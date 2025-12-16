#!/usr/bin/env python
# _*_ coding:utf-8 _*_
import logging
import os
import re
import arrow
import sqlite3
from contextlib import closing
from os.path import join, exists
from werkzeug.utils import secure_filename
from xmind2testcase.zentao import xmind_to_zentao_csv_file
from xmind2testcase.testlink import xmind_to_testlink_xml_file
from xmind2testcase.utils import get_xmind_testsuites, get_xmind_testcase_list
from flask import Flask, request, send_from_directory, g, render_template, abort, redirect, url_for

here = os.path.abspath(os.path.dirname(__file__))
log_file = os.path.join(here, 'running.log')
# log handler
formatter = logging.Formatter('%(asctime)s  %(name)s  %(levelname)s  [%(module)s - %(funcName)s]: %(message)s')
file_handler = logging.FileHandler(log_file, encoding='UTF-8')
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.DEBUG)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
stream_handler.setLevel(logging.INFO)
# xmind to testcase logger
root_logger = logging.getLogger()
root_logger.addHandler(file_handler)
root_logger.addHandler(stream_handler)
root_logger.setLevel(logging.DEBUG)
# flask and werkzeug logger
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.addHandler(file_handler)
werkzeug_logger.addHandler(stream_handler)
werkzeug_logger.setLevel(logging.DEBUG)

# global variable
UPLOAD_FOLDER = os.path.join(here, 'uploads')
ALLOWED_EXTENSIONS = ['xmind']
DEBUG = True
DATABASE = os.path.join(here, 'data.db3')
HOST = '0.0.0.0'

# flask app
app = Flask(__name__)
app.config.from_object(__name__)
app.secret_key = os.urandom(32)
# 配置：保留记录数量、分批大小、重试次数
app.config['RECORDS_KEEP'] = 1
app.config['CLEANUP_BATCH_SIZE'] = 200
app.config['CLEANUP_RETRY_COUNT'] = 3


def connect_db():
    return sqlite3.connect(app.config['DATABASE'])


def init_db():
    with closing(connect_db()) as db:
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()


def ensure_db_indexes():
    """
    函数：ensure_db_indexes
    作用：确保数据库存在必要索引以提升查询与清理性能
    参数：无
    返回：无
    """
    with closing(connect_db()) as db:
        c = db.cursor()
        c.execute("CREATE INDEX IF NOT EXISTS idx_records_is_deleted_id ON records(is_deleted, id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_records_name ON records(name)")
        db.commit()


def init():
    app.logger.info('Start initializing the database...')
    if not exists(UPLOAD_FOLDER):
        os.mkdir(UPLOAD_FOLDER)

    if not exists(DATABASE):
        init_db()
    # 确保索引存在
    ensure_db_indexes()
    app.logger.info('Congratulations! the xmind2testcase webtool database has initialized successfully!')


@app.before_request
def before_request():
    g.db = connect_db()


@app.teardown_request
def teardown_request(exception):
    db = getattr(g, 'db', None)
    if db is not None:
        db.close()


def insert_record(xmind_name, note=''):
    """
    函数：insert_record
    作用：插入一条记录（不含清理逻辑）
    参数：xmind_name - 文件名；note - 备注
    返回：无（直接提交）
    """
    c = g.db.cursor()
    now = str(arrow.now())
    sql = "INSERT INTO records (name,create_on,note) VALUES (?,?,?)"
    c.execute(sql, (xmind_name, now, str(note)))
    g.db.commit()


def _chunked(iterable, size):
    """
    函数：_chunked
    作用：将可迭代对象按固定大小切分，便于分批处理，降低一次性I/O成本
    参数：iterable - 可迭代对象；size - 每批大小
    返回：生成器，逐批返回列表
    """
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def mark_and_delete_old_records(c, keep, batch_size):
    """
    函数：mark_and_delete_old_records
    作用：查询并标记所有旧记录为删除，并分批删除对应上传/导出文件
    参数：c - sqlite游标；keep - 保留数量；batch_size - 文件删除批大小
    返回：元组 (rows_deleted, files_removed)
    """
    c.execute("SELECT id, name FROM records WHERE is_deleted<>1 ORDER BY id DESC LIMIT -1 OFFSET ?", (int(keep),))
    rows = c.fetchall()  # [(id, name), ...]
    for r in rows:
        c.execute('UPDATE records SET is_deleted=1 WHERE id=?', (r[0],))

    files_removed = 0
    for batch in _chunked(rows, int(batch_size)):
        for (_id, name) in batch:
            xmind_file = join(app.config['UPLOAD_FOLDER'], name)
            testlink_file = join(app.config['UPLOAD_FOLDER'], name[:-5] + 'xml')
            zentao_file = join(app.config['UPLOAD_FOLDER'], name[:-5] + 'csv')
            for f in [xmind_file, testlink_file, zentao_file]:
                if exists(f):
                    os.remove(f)
                    files_removed += 1
    return len(rows), files_removed


def insert_record_and_cleanup(xmind_name, note='', keep=None, batch_size=None, retry=None):
    """
    函数：insert_record_and_cleanup
    作用：在单事务中插入新记录并标记/删除所有历史记录，仅保留最新keep条（默认取配置）
    参数：
      - xmind_name：新文件名
      - note：备注
      - keep：保留条数（缺省取 app.config['RECORDS_KEEP']）
      - batch_size：批量删除批大小（缺省取 app.config['CLEANUP_BATCH_SIZE']）
      - retry：并发冲突重试次数（缺省取 app.config['CLEANUP_RETRY_COUNT']）
    返回：True 表示成功；异常将被抛出并在上层处理
    """
    import time
    keep = app.config.get('RECORDS_KEEP', 1) if keep is None else int(keep)
    batch_size = app.config.get('CLEANUP_BATCH_SIZE', 200) if batch_size is None else int(batch_size)
    retry = app.config.get('CLEANUP_RETRY_COUNT', 3) if retry is None else int(retry)

    attempts = 0
    while attempts < retry:
        try:
            c = g.db.cursor()
            c.execute('BEGIN IMMEDIATE')
            start_ts = time.perf_counter()

            now = str(arrow.now())
            c.execute("INSERT INTO records (name,create_on,note) VALUES (?,?,?)", (xmind_name, now, str(note)))

            rows_deleted, files_removed = mark_and_delete_old_records(c, keep=keep, batch_size=batch_size)

            g.db.commit()
            cost = (time.perf_counter() - start_ts) * 1000.0
            app.logger.info('Insert+Cleanup success | keep=%s rows_deleted=%s files_removed=%s cost=%.2fms', keep, rows_deleted, files_removed, cost)
            return True

        except sqlite3.OperationalError as e:
            attempts += 1
            try:
                g.db.rollback()
            except Exception:
                pass
            app.logger.warning('Insert+Cleanup locking conflict | attempt=%s error=%s', attempts, e)
            if attempts >= retry:
                raise
        except Exception as e:
            try:
                g.db.rollback()
            except Exception:
                pass
            app.logger.error('Insert+Cleanup failed: %s', e)
            raise


def delete_record(filename, record_id):
    xmind_file = join(app.config['UPLOAD_FOLDER'], filename)
    testlink_file = join(app.config['UPLOAD_FOLDER'], filename[:-5] + 'xml')
    zentao_file = join(app.config['UPLOAD_FOLDER'], filename[:-5] + 'csv')

    for f in [xmind_file, testlink_file, zentao_file]:
        if exists(f):
            os.remove(f)

    c = g.db.cursor()
    sql = 'UPDATE records SET is_deleted=1 WHERE id = ?'
    c.execute(sql, (record_id,))
    g.db.commit()


def delete_records(keep=20):
    """Clean up files on server and mark the record as deleted"""
    sql = "SELECT * from records where is_deleted<>1 ORDER BY id desc LIMIT -1 offset {}".format(keep)
    assert isinstance(g.db, sqlite3.Connection)
    c = g.db.cursor()
    c.execute(sql)
    rows = c.fetchall()
    for row in rows:
        name = row[1]
        xmind_file = join(app.config['UPLOAD_FOLDER'], name)
        testlink_file = join(app.config['UPLOAD_FOLDER'], name[:-5] + 'xml')
        zentao_file = join(app.config['UPLOAD_FOLDER'], name[:-5] + 'csv')

        for f in [xmind_file, testlink_file, zentao_file]:
            if exists(f):
                os.remove(f)

        sql = 'UPDATE records SET is_deleted=1 WHERE id = ?'
        c.execute(sql, (row[0],))
        g.db.commit()


def get_latest_record():
    found = list(get_records(1))
    if found:
        return found[0]


def get_records(limit=8):
    """
    获取最近的上传记录并返回用于页面展示的简化数据。
    - 参数：limit 指定返回记录的最大数量。
    - 处理：
      1) 对过长的文件名进行截断以适配表格展示；
      2) 使用 Arrow 的 humanize(locale='zh_cn') 将时间人性化并本地化为中文；
    - 返回：生成器，元素为 (short_name, name, create_on, note, record_id)
    """
    short_name_length = 120
    c = g.db.cursor()
    sql = "select * from records where is_deleted<>1 order by id desc limit {}".format(int(limit))
    c.execute(sql)
    rows = c.fetchall()

    for row in rows:
        name, short_name, create_on, note, record_id = row[1], row[1], row[2], row[3], row[0]

        # shorten the name for display
        if len(name) > short_name_length:
            short_name = name[:short_name_length] + '...'

        # more readable time format (localized to Chinese)
        create_on = arrow.get(create_on).humanize(locale='zh_cn')
        yield short_name, name, create_on, note, record_id


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS


def check_file_name(name):
    secured = secure_filename(name)
    if not secured:
        secured = re.sub('[^\w\d]+', '_', name)  # only keep letters and digits from file name
        assert secured, 'Unable to parse file name: {}!'.format(name)
    return secured + '.xmind'


def save_file(file):
    """
    函数：save_file
    作用：保存上传文件；使用事务化插入+清理，仅保留最新记录
    参数：file - Flask 上传的文件对象
    返回：成功时返回文件名，失败返回 None 并在 g 中标记错误
    """
    if file and allowed_file(file.filename):
        # filename = check_file_name(file.filename[:-6])
        filename = file.filename
        upload_to = join(app.config['UPLOAD_FOLDER'], filename)

        if exists(upload_to):
            filename = '{}_{}.xmind'.format(filename[:-6], arrow.now().strftime('%Y%m%d_%H%M%S'))
            upload_to = join(app.config['UPLOAD_FOLDER'], filename)

        file.save(upload_to)
        try:
            # 使用事务化插入并清理，仅保留最新1条记录
            insert_record_and_cleanup(filename, note='', keep=1, batch_size=200, retry=3)
            g.is_success = True
            return filename
        except Exception as e:
            # 数据库插入或清理失败时，删除已保存的文件并提示错误
            try:
                if exists(upload_to):
                    os.remove(upload_to)
            except Exception:
                pass
            g.is_success = False
            g.error = f"保存失败：{e}"
            return None

    elif file.filename == '':
        g.is_success = False
        g.error = "Please select a file!"

    else:
        g.is_success = False
        g.invalid_files.append(file.filename)


def verify_uploaded_files(files):
    # download the xml directly if only 1 file uploaded
    if len(files) == 1 and getattr(g, 'is_success', False):
        g.download_xml = get_latest_record()[1]

    if g.invalid_files:
        g.error = "Invalid file: {}".format(','.join(g.invalid_files))


@app.route('/', methods=['GET', 'POST'])
def index(download_xml=None):
    """
    函数：index
    作用：首页展示与上传入口；上传成功后跳转预览；首页仅展示最新记录
    参数：download_xml - 可选，单文件上传时直接提供下载
    返回：渲染模板或重定向
    """
    g.invalid_files = []
    g.error = None
    g.download_xml = download_xml
    g.filename = None

    if request.method == 'POST':
        if 'file' not in request.files:
            return redirect(request.url)

        file = request.files['file']

        if file.filename == '':
            return redirect(request.url)

        g.filename = save_file(file)
        verify_uploaded_files([file])
        # 自动清理已在事务中完成，仅保留最新记录

    else:
        g.upload_form = True

    if g.filename:
        return redirect(url_for('preview_file', filename=g.filename))
    else:
        return render_template('index.html', records=list(get_records(1)))


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/<filename>/to/testlink')
def download_testlink_file(filename):
    full_path = join(app.config['UPLOAD_FOLDER'], filename)

    if not exists(full_path):
        abort(404)

    testlink_xmls_file = xmind_to_testlink_xml_file(full_path)
    filename = os.path.basename(testlink_xmls_file) if testlink_xmls_file else abort(404)

    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)


@app.route('/<filename>/to/zentao')
def download_zentao_file(filename):
    full_path = join(app.config['UPLOAD_FOLDER'], filename)

    if not exists(full_path):
        abort(404)

    zentao_csv_file = xmind_to_zentao_csv_file(full_path)
    filename = os.path.basename(zentao_csv_file) if zentao_csv_file else abort(404)

    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)


@app.route('/preview/<filename>')
def preview_file(filename):
    full_path = join(app.config['UPLOAD_FOLDER'], filename)

    if not exists(full_path):
        abort(404)

    testsuites = get_xmind_testsuites(full_path)
    suite_count = 0
    for suite in testsuites:
        suite_count += len(suite.sub_suites)

    testcases = get_xmind_testcase_list(full_path)

    return render_template('preview.html', name=filename, suite=testcases, suite_count=suite_count)


@app.route('/delete/<filename>/<int:record_id>')
def delete_file(filename, record_id):

    full_path = join(app.config['UPLOAD_FOLDER'], filename)
    if not exists(full_path):
        abort(404)
    else:
        delete_record(filename, record_id)
    return redirect('/')


@app.route('/cleanup', methods=['POST'])
def cleanup():
    """
    函数：cleanup
    作用：手动清理历史记录，仅保留最新1条；POST方式并带确认字段。
    返回：完成后重定向到首页
    安全：简单防误触，要求 confirm=yes
    审计：记录客户端IP与UA
    """
    import time
    confirm = request.form.get('confirm')
    if confirm != 'yes':
        return redirect(url_for('index'))
    try:
        c = g.db.cursor()
        c.execute('BEGIN IMMEDIATE')
        start_ts = time.perf_counter()
        keep = app.config.get('RECORDS_KEEP', 1)
        batch_size = app.config.get('CLEANUP_BATCH_SIZE', 200)
        rows_deleted, files_removed = mark_and_delete_old_records(c, keep=keep, batch_size=batch_size)
        g.db.commit()
        cost = (time.perf_counter() - start_ts) * 1000.0
        app.logger.info('Manual cleanup completed | ip=%s ua=%s keep=%s rows_deleted=%s files_removed=%s cost=%.2fms', request.remote_addr, request.headers.get('User-Agent',''), keep, rows_deleted, files_removed, cost)
    except Exception as e:
        try:
            g.db.rollback()
        except Exception:
            pass
        app.logger.error('Manual cleanup failed | ip=%s error=%s', request.remote_addr, e)
    return redirect(url_for('index'))


@app.errorhandler(Exception)
def app_error(e):
    return str(e)


def launch(host=HOST, debug=True, port=5002):
    init()  # initializing the database
    app.run(host=host, debug=debug, port=port)


if __name__ == '__main__':
    init()  # initializing the database
    app.run(HOST, debug=DEBUG, port=5002)
