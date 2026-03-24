#!/usr/bin/env bash

# 进入项目根目录
cd "$(dirname "$0")"

PID_FILE="webtool.pid"

echo "========================================================"
echo "准备停止 XmindTestCase WebTool 服务..."
echo "========================================================"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    # 检查进程是否存在
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "发现运行中的服务，正在结束进程 PID: $PID..."
        kill "$PID"
        
        # 等待进程结束
        sleep 2
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "服务未能正常停止，尝试强制结束..."
            kill -9 "$PID"
        fi
        
        echo "服务已成功停止。"
        rm -f "$PID_FILE"
    else
        echo "进程 PID: $PID 已不存在。清理过期的 $PID_FILE 文件。"
        rm -f "$PID_FILE"
    fi
else
    echo "未找到 $PID_FILE 文件。尝试通过进程名称查找..."
    
    # 通过进程名称查找（匹配 python webtool/application.py）
    PIDS=$(pgrep -f "python webtool/application.py")
    
    if [ -n "$PIDS" ]; then
        for P in $PIDS; do
            echo "发现残留服务进程 PID: $P，正在结束..."
            kill "$P"
            sleep 1
            if ps -p "$P" > /dev/null 2>&1; then
                kill -9 "$P"
            fi
        done
        echo "所有相关的服务进程均已结束。"
    else
        echo "没有找到正在运行的服务。"
    fi
fi
