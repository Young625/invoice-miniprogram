#!/bin/bash

# 简单的后台启动脚本（使用 nohup）

SCRIPT_DIR="/data/kaipiaoxia/code/backend"
cd "$SCRIPT_DIR"

# 激活 conda 环境
source /root/miniconda3/etc/profile.d/conda.sh
conda activate invoice-backend

# 按日期确定日志目录和文件
LOG_YEAR_MONTH=$(date +%Y-%m)
LOG_DATE=$(date +%Y-%m-%d)
LOG_DIR="logs/$LOG_YEAR_MONTH"
LOG_FILE="$LOG_DIR/application.log"

mkdir -p "$LOG_DIR"

# 写入启动记录
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ===== 服务启动 =====" >> "$LOG_FILE"

# 启动服务（所有日志通过 Python logging 框架写入按日期轮转的文件）
# python main.py 会先执行 setup_logging()，再启动 uvicorn，
# uvicorn 的启动/访问/错误日志也会流入同一套日志文件
nohup python main.py >> "$LOG_FILE" 2>&1 &

# 获取进程 ID
PID=$!

# 保存 PID 到文件
echo $PID > logs/app.pid

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 服务已启动，PID: $PID" >> "$LOG_FILE"

echo "服务已启动，PID: $PID"
echo "日志文件: $LOG_FILE"
echo ""
echo "停止服务: ./stop.sh"
