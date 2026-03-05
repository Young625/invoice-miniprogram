#!/bin/bash

# 简单的后台启动脚本（使用 nohup）

SCRIPT_DIR="/data/kaipiaoxia/code/backend"
cd "$SCRIPT_DIR"

# 激活 conda 环境
source /root/miniconda3/etc/profile.d/conda.sh
conda activate invoice-backend

# 创建日志目录
mkdir -p logs

# 启动服务（使用 >> 追加日志，保留历史记录）
nohup uvicorn main:app --host 0.0.0.0 --port 8000 >> logs/nohup.log 2>&1 &

# 获取进程 ID
PID=$!

# 保存 PID 到文件
echo $PID > logs/app.pid

echo "服务已启动，PID: $PID"
echo "日志文件: logs/app.log (应用日志)"
echo "         logs/nohup.log (启动日志)"
echo ""
echo "停止服务: kill $PID"
echo "或使用: ./stop.sh"
