#!/bin/bash

# 停止服务脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/logs/app.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")

    if ps -p $PID > /dev/null 2>&1; then
        echo "正在停止服务 (PID: $PID)..."
        kill $PID

        # 等待进程结束
        sleep 2

        if ps -p $PID > /dev/null 2>&1; then
            echo "进程未响应，强制终止..."
            kill -9 $PID
        fi

        rm -f "$PID_FILE"
        echo "服务已停止"
    else
        echo "进程不存在 (PID: $PID)"
        rm -f "$PID_FILE"
    fi
else
    echo "PID 文件不存在，尝试查找进程..."

    # 查找 uvicorn 进程
    PIDS=$(ps aux | grep "uvicorn main:app" | grep -v grep | awk '{print $2}')

    if [ -n "$PIDS" ]; then
        echo "找到以下进程："
        ps aux | grep "uvicorn main:app" | grep -v grep
        echo ""
        echo "是否要停止这些进程? (y/n)"
        read -r response

        if [ "$response" = "y" ]; then
            for pid in $PIDS; do
                echo "停止进程 $pid..."
                kill $pid
            done
            echo "服务已停止"
        fi
    else
        echo "未找到运行中的服务"
    fi
fi
