#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import zipfile
import tempfile
import shutil
import logging
import time
from datetime import datetime
from functools import lru_cache
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 全局缓存，用于存储已解析的文件内容
_file_cache = {}
_cache_max_size = 100  # 最大缓存文件数


def _get_file_cache_key(file_path):
    """获取文件缓存键"""
    try:
        stat = os.stat(file_path)
        return f"{file_path}_{stat.st_mtime}_{stat.st_size}"
    except Exception:
        return file_path


def _get_cached_data(file_path):
    """从缓存获取数据"""
    cache_key = _get_file_cache_key(file_path)
    return _file_cache.get(cache_key)


def _set_cached_data(file_path, data):
    """设置缓存数据"""
    global _file_cache
    
    # 如果缓存已满，清理最旧的条目
    if len(_file_cache) >= _cache_max_size:
        oldest_key = min(_file_cache.keys(), key=lambda k: _file_cache[k].get('timestamp', 0))
        del _file_cache[oldest_key]
    
    cache_key = _get_file_cache_key(file_path)
    _file_cache[cache_key] = {
        'data': data,
        'timestamp': time.time()
    }


def _clear_cache():
    """清理缓存"""
    global _file_cache
    _file_cache.clear()


class XmindLoadError(Exception):
    """XMind文件加载错误"""
    
    def __init__(self, error_type, message, details=None):
        self.error_type = error_type
        self.message = message
        self.details = details or {}
        super().__init__(self.__str__())
    
    def __str__(self):
        error_msg = f"[{self.error_type}] {self.message}"
        if self.details:
            details_str = ", ".join([f"{k}={v}" for k, v in self.details.items()])
            error_msg += f" ({details_str})"
        return error_msg


class XmindLoaderDebugger:
    """XMind加载调试器"""
    
    def __init__(self, enable_debug=True):
        self.enable_debug = enable_debug
        self.debug_info = {
            'start_time': None,
            'end_time': None,
            'file_size': 0,
            'extract_time': 0,
            'parse_time': 0,
            'convert_time': 0,
            'temp_dir': None,
            'extracted_files': [],
            'content_structure': {},
            'errors': []
        }
        self.start_time = None
    
    def start_debug(self, xmind_file):
        """开始调试记录"""
        if not self.enable_debug:
            return
        
        import time
        self.debug_info['start_time'] = time.time()
        self.debug_info['file_size'] = os.path.getsize(xmind_file)
        logger.info(f"开始加载XMind文件: {xmind_file} (大小: {self.debug_info['file_size']} bytes)")
    
    def log_extract_time(self, start_time, extracted_files):
        """记录解压时间"""
        if not self.enable_debug:
            return
        
        import time
        self.debug_info['extract_time'] = time.time() - start_time
        self.debug_info['extracted_files'] = extracted_files
        logger.info(f"解压完成: {len(extracted_files)}个文件, 耗时: {self.debug_info['extract_time']:.3f}s")
    
    def log_parse_time(self, start_time, content_data):
        """记录解析时间"""
        if not self.enable_debug:
            return
        
        import time
        self.debug_info['parse_time'] = time.time() - start_time
        self.debug_info['content_structure'] = self._analyze_content_structure(content_data)
        logger.info(f"JSON解析完成, 耗时: {self.debug_info['parse_time']:.3f}s")
    
    def _analyze_content_structure(self, content_data):
        """分析content.json结构"""
        structure = {
            'sheet_count': 0,
            'topic_count': 0,
            'max_depth': 0
        }
        
        if content_data and 'sheets' in content_data:
            structure['sheet_count'] = len(content_data['sheets'])
            for sheet in content_data['sheets']:
                if 'topic' in sheet:
                    topic_stats = self._count_topics(sheet['topic'])
                    structure['topic_count'] += topic_stats['count']
                    structure['max_depth'] = max(structure['max_depth'], topic_stats['max_depth'])
        
        return structure
    
    def _count_topics(self, topic, depth=0):
        """统计主题信息"""
        stats = {'count': 1, 'max_depth': depth}
        
        if 'topics' in topic and topic['topics']:
            for sub_topic in topic['topics']:
                sub_stats = self._count_topics(sub_topic, depth + 1)
                stats['count'] += sub_stats['count']
                stats['max_depth'] = max(stats['max_depth'], sub_stats['max_depth'])
        
        return stats
    
    def get_debug_report(self):
        """获取调试报告"""
        if not self.enable_debug:
            return None
        
        import time
        self.debug_info['end_time'] = time.time()
        total_time = self.debug_info['end_time'] - self.debug_info['start_time']
        
        return {
            '性能统计': {
                '总耗时': f"{total_time:.3f}s",
                '解压耗时': f"{self.debug_info['extract_time']:.3f}s",
                '解析耗时': f"{self.debug_info['parse_time']:.3f}s",
                '转换耗时': f"{self.debug_info['convert_time']:.3f}s"
            },
            '文件信息': {
                '文件大小': f"{self.debug_info['file_size']} bytes",
                '临时目录': self.debug_info['temp_dir'],
                '解压文件数': len(self.debug_info['extracted_files'])
            },
            '内容结构': self.debug_info['content_structure'],
            '错误记录': self.debug_info['errors']
        }


def validate_xmind_file(xmind_file):
    """验证XMind文件完整性"""
    try:
        # 检查文件是否存在
        if not os.path.exists(xmind_file):
            raise FileNotFoundError(f"XMind文件不存在: {xmind_file}")
        
        # 检查文件扩展名
        if not xmind_file.lower().endswith('.xmind'):
            raise ValueError(f"文件扩展名不是.xmind: {xmind_file}")
        
        # 检查文件大小
        file_size = os.path.getsize(xmind_file)
        if file_size == 0:
            raise ValueError("XMind文件大小为0")
        
        # 尝试作为ZIP文件打开
        with zipfile.ZipFile(xmind_file, 'r') as zip_ref:
            if zip_ref.testzip() is not None:
                raise zipfile.BadZipFile("XMind文件包含损坏的压缩数据")
            
            # 检查必需的文件
            file_list = zip_ref.namelist()
            if 'content.json' not in file_list:
                raise ValueError("XMind文件中缺少content.json")
        
        return True
        
    except Exception as e:
        logger.error(f"XMind文件验证失败: {str(e)}")
        return False


class ContentJsonParser:
    """content.json解析器"""
    
    def __init__(self, extract_dir):
        self.extract_dir = extract_dir
        self.content_data = None
        self.metadata = {}
    
    def parse_content_json(self):
        """解析content.json文件"""
        content_path = os.path.join(self.extract_dir, 'content.json')
        
        if not os.path.exists(content_path):
            raise FileNotFoundError(f"content.json文件不存在: {content_path}")
        
        try:
            with open(content_path, 'r', encoding='utf-8') as f:
                self.content_data = json.load(f)
            
            # 验证数据结构
            self._validate_content_structure()
            
            # 加载附加信息
            self._load_additional_data()
            
            return self.content_data
            
        except json.JSONDecodeError as e:
            raise ValueError(f"content.json文件格式错误: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"解析content.json失败: {str(e)}")
    
    def _validate_content_structure(self):
        """验证content.json数据结构"""
        # 处理旧格式（content.json是数组）
        if isinstance(self.content_data, list):
            if len(self.content_data) == 0:
                raise ValueError("content.json数组不能为空")
            return
        
        # 处理新格式（content.json是对象）
        if not isinstance(self.content_data, dict):
            raise ValueError("content.json根元素必须是对象或数组")
        
        if 'sheets' not in self.content_data:
            raise ValueError("content.json缺少sheets字段")
        
        if not isinstance(self.content_data['sheets'], list):
            raise ValueError("sheets字段必须是数组")
        
        if len(self.content_data['sheets']) == 0:
            raise ValueError("sheets数组不能为空")
    
    def _load_additional_data(self):
        """加载附加数据文件"""
        # 加载metadata.json
        metadata_path = os.path.join(self.extract_dir, 'metadata.json')
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)
            except Exception as e:
                logger.warning(f"加载metadata.json失败: {str(e)}")


class DataFormatConverter:
    """数据格式转换器，确保与原有格式兼容"""
    
    def convert_to_xmind_format(self, content_data):
        """转换为与原有xmind库兼容的格式"""
        result = []
        
        if not content_data:
            return result
        
        # 处理旧格式（content.json是数组）
        if isinstance(content_data, list):
            for sheet in content_data:
                # 直接使用原始数据，只转换必要的字段
                converted_sheet = {
                    'id': sheet.get('id', ''),
                    'title': sheet.get('title'),  # 保留原始标题
                    'topic': self._convert_topic(sheet.get('topic', sheet.get('rootTopic', {})))
                }
                result.append(converted_sheet)
            return result
        
        # 处理新格式（content.json是对象）
        if 'sheets' not in content_data:
            return result
        
        for sheet in content_data['sheets']:
            converted_sheet = {
                'id': sheet.get('id', ''),
                'title': sheet.get('title'),  # 保留原始标题
                'topic': self._convert_topic(sheet.get('topic', {}))
            }
            result.append(converted_sheet)
        
        return result
    
    def _convert_topic(self, topic_data):
        """转换主题数据（兼容新版XMind结构）"""
        if not topic_data:
            import uuid
            topic_id = str(uuid.uuid4()).replace('-', '')[:26]
            return {
                'id': topic_id,
                'link': None,
                'title': None,
                'note': None,
                'label': None,
                'comment': None,
                'markers': [],
                'topics': []
            }
        
        # 标题
        title = topic_data.get('title')
        
        # 备注（notes -> note）
        note = topic_data.get('note')
        if not note:
            notes = topic_data.get('notes')
            if isinstance(notes, dict):
                plain = notes.get('plain')
                if isinstance(plain, dict):
                    note = plain.get('content')
        
        # 标签/评论原样透传（若存在）
        label = topic_data.get('label')
        comment = topic_data.get('comment')
        
        # 标记（markers 可能为对象列表，需要转换为字符串ID列表）
        raw_markers = topic_data.get('markers', [])
        markers = []
        if isinstance(raw_markers, list):
            for m in raw_markers:
                if isinstance(m, dict):
                    mid = m.get('markerId') or m.get('id')
                    if isinstance(mid, str):
                        markers.append(mid)
                elif isinstance(m, str):
                    markers.append(m)
        
        # 子主题（新版在 children.attached 中）
        topics = topic_data.get('topics')
        if not isinstance(topics, list):
            topics = []
        
        children = topic_data.get('children')
        if isinstance(children, dict):
            attached = children.get('attached')
            if isinstance(attached, list):
                for child in attached:
                    topics.append(self._convert_topic(child))
        
        result = {
            'id': topic_data.get('id', ''),
            'link': topic_data.get('link'),
            'title': title,
            'note': note,
            'label': label,
            'comment': comment,
            'markers': markers,
            'topics': topics
        }
        
        return result
    
    def _convert_topics(self, topics_data):
        """转换子主题列表"""
        if not topics_data:
            return []
        
        result = []
        for topic_data in topics_data:
            result.append(self._convert_topic(topic_data))
        
        return result


class XmindFileLoader:
    """XMind文件加载器，替代xmind库的功能"""
    
    def __init__(self, xmind_file, enable_debug=False):
        self.xmind_file = xmind_file
        self.temp_dir = None
        self.content_data = None
        self.debugger = XmindLoaderDebugger(enable_debug)
    
    def load(self, enable_debug=False):
        """加载XMind文件并返回数据"""
        debug_info = {}
        
        if enable_debug and self.debugger and hasattr(self.debugger, 'start_debug'):
            self.debugger.start_debug(self.xmind_file)
        
        # 检查缓存
        cached_data = _get_cached_data(self.xmind_file)
        if cached_data:
            self.content_data = cached_data['data']
            logger.debug(f"从缓存加载文件: {self.xmind_file}")
            return self.content_data
        
        try:
            # 验证文件
            if not validate_xmind_file(self.xmind_file):
                raise XmindLoadError("FILE_VALIDATION", "XMind文件验证失败", 
                                   {"file": self.xmind_file})
            
            # 解压文件
            extract_start = time.time()
            extract_dir = self._extract_xmind_file()
            extracted_files = os.listdir(extract_dir) if os.path.exists(extract_dir) else []
            if enable_debug and self.debugger and hasattr(self.debugger, 'log_extract_time'):
                self.debugger.log_extract_time(extract_start, extracted_files)
            
            # 解析content.json
            parse_start = time.time()
            parser = ContentJsonParser(extract_dir)
            content_data = parser.parse_content_json()
            if enable_debug and self.debugger and hasattr(self.debugger, 'log_parse_time'):
                self.debugger.log_parse_time(parse_start, content_data)
            
            # 转换为兼容格式
            converter = DataFormatConverter()
            self.content_data = converter.convert_to_xmind_format(content_data)
            
            # 缓存结果
            _set_cached_data(self.xmind_file, self.content_data)
            
            # 清理临时目录
            self._cleanup()
            
            logger.info(f"✅ XMind文件加载成功: {self.xmind_file}")
            return self.content_data
            
        except XmindLoadError:
            self._cleanup()
            raise
        except Exception as e:
            self._cleanup()
            logger.error(f"❌ XMind文件加载失败: {str(e)}")
            raise XmindLoadError("LOAD_FAILED", f"加载XMind文件失败: {str(e)}", 
                               {"file": self.xmind_file})
    
    def _extract_xmind_file(self):
        """解压XMind文件"""
        try:
            # 创建临时目录
            self.temp_dir = tempfile.mkdtemp(prefix='xmind_extract_')
            
            # 解压文件
            with zipfile.ZipFile(self.xmind_file, 'r') as zip_ref:
                zip_ref.extractall(self.temp_dir)
            
            return self.temp_dir
            
        except zipfile.BadZipFile as e:
            raise XmindLoadError("BAD_ZIP_FILE", "XMind文件ZIP格式错误", 
                               {"error": str(e)})
        except Exception as e:
            raise XmindLoadError("EXTRACTION_FAILED", "XMind文件解压失败", 
                               {"error": str(e)})
    
    def getData(self):
        """获取解析后的数据，兼容原有xmind库接口"""
        return self.content_data if self.content_data else []
    
    def get_debug_info(self):
        """获取调试信息"""
        return self.debugger.get_debug_report() if self.debugger else {}
    
    def _cleanup(self):
        """清理临时资源"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                logger.debug(f"清理临时目录: {self.temp_dir}")
            except Exception as e:
                logger.warning(f"清理临时目录失败: {str(e)}")
    
    def __del__(self):
        """析构函数"""
        self._cleanup()


class XmindWorkbookWrapper:
    """工作簿包装器，提供与原有xmind库兼容的API"""
    
    def __init__(self, data, debug_info=None):
        self._data = data
        self._debug_info = debug_info or {}
    
    def getData(self):
        """获取工作簿数据，兼容原有xmind库的API"""
        return self._data
    
    def get_debug_info(self):
        """获取调试信息"""
        return self._debug_info
    
    def __len__(self):
        """支持len()函数"""
        return len(self._data) if self._data else 0


# 兼容原有xmind库的接口
def load(xmind_file, enable_debug=False):
    """
    加载XMind文件的入口函数
    
    Args:
        xmind_file: XMind文件路径
        enable_debug: 是否启用调试模式
    
    Returns:
        XmindWorkbookWrapper: 包含加载数据和调试信息的包装器对象
    """
    loader = XmindFileLoader(xmind_file)
    
    try:
        result = loader.load(enable_debug)
        debug_info = {}
        
        if enable_debug and loader.debugger:
            debug_info = loader.get_debug_info()
        
        return XmindWorkbookWrapper(result, debug_info)
        
    except Exception as e:
        logger.error(f"加载XMind文件失败: {str(e)}")
        raise