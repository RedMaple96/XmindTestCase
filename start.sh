#!/usr/bin/env bash

# 进入项目根目录
cd "$(dirname "$0")"

WEBTOOL_DIR="webtool"
CERT_FILE="${WEBTOOL_DIR}/cert.pem"
KEY_FILE="${WEBTOOL_DIR}/key.pem"

# 1. 检查并生成自签名证书 (如果不存在)
if [ ! -f "$CERT_FILE" ] || [ ! -f "$KEY_FILE" ]; then
    echo "========================================================"
    echo "未检测到 HTTPS 证书，正在生成自签名证书..."
    echo "========================================================"
    openssl req -x509 -newkey rsa:4096 -nodes -out "$CERT_FILE" -keyout "$KEY_FILE" -days 3650 -subj "/C=CN/ST=Beijing/L=Beijing/O=XmindTestCase/CN=localhost"
    echo "证书已生成: $CERT_FILE, $KEY_FILE"
fi

# 2. 检查应用是否已经在运行
PID_FILE="webtool.pid"
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "服务已经在运行中 (PID: $PID)。请先执行 stop.sh 停止服务。"
        exit 1
    else
        # 进程已不存在，清理过期的 pid 文件
        rm -f "$PID_FILE"
    fi
fi

# 3. 后台启动服务
echo "========================================================"
echo "正在启动 XmindTestCase WebTool (HTTPS)..."
echo "========================================================"

# 设置 PYTHONPATH 以便能够找到 xmind2testcase 模块，并使用 nohup 运行 python
export PYTHONPATH="$(pwd)"
nohup python webtool/application.py > webtool.log 2>&1 &
PID=$!

# 保存 PID
echo $PID > "$PID_FILE"

echo "服务启动成功，进程ID: $PID"
echo "日志输出至: webtool.log"
echo "请访问: https://127.0.0.1:5172"
