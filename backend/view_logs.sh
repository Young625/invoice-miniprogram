#!/bin/bash

# 日志查看脚本

SCRIPT_DIR="/data/kaipiaoxia/code/backend"
cd "$SCRIPT_DIR"

echo "==================================="
echo "发票管理系统 - 日志查看工具"
echo "==================================="
echo ""

# 检查日志目录是否存在
if [ ! -d "logs" ]; then
    echo "❌ 日志目录不存在"
    exit 1
fi

# 获取当前年月
CURRENT_MONTH=$(date +%Y-%m)
CURRENT_LOG_DIR="logs/$CURRENT_MONTH"

# 显示菜单
echo "当前月份: $CURRENT_MONTH"
echo ""
echo "请选择要查看的日志:"
echo "1) 应用日志 (application.log) - 最新50行"
echo "2) 错误日志 (application-error.log) - 最新50行"
echo "3) 启动日志 (nohup.log) - 最新50行"
echo "4) 应用日志 - 实时监控"
echo "5) 错误日志 - 实时监控"
echo "6) 查看历史日志(压缩文件)"
echo "7) 查看所有日志文件"
echo "8) 搜索日志内容"
echo ""
read -p "请输入选项 (1-8): " choice

case $choice in
    1)
        if [ -f "$CURRENT_LOG_DIR/application.log" ]; then
            echo ""
            echo "=== 应用日志 (最新50行) ==="
            tail -n 50 "$CURRENT_LOG_DIR/application.log"
        else
            echo "❌ 日志文件不存在: $CURRENT_LOG_DIR/application.log"
        fi
        ;;
    2)
        if [ -f "$CURRENT_LOG_DIR/application-error.log" ]; then
            echo ""
            echo "=== 错误日志 (最新50行) ==="
            tail -n 50 "$CURRENT_LOG_DIR/application-error.log"
        else
            echo "❌ 日志文件不存在: $CURRENT_LOG_DIR/application-error.log"
        fi
        ;;
    3)
        if [ -f "logs/nohup.log" ]; then
            echo ""
            echo "=== 启动日志 (最新50行) ==="
            tail -n 50 logs/nohup.log
        else
            echo "❌ 日志文件不存在: logs/nohup.log"
        fi
        ;;
    4)
        if [ -f "$CURRENT_LOG_DIR/application.log" ]; then
            echo ""
            echo "=== 应用日志 (实时监控，按 Ctrl+C 退出) ==="
            tail -f "$CURRENT_LOG_DIR/application.log"
        else
            echo "❌ 日志文件不存在: $CURRENT_LOG_DIR/application.log"
        fi
        ;;
    5)
        if [ -f "$CURRENT_LOG_DIR/application-error.log" ]; then
            echo ""
            echo "=== 错误日志 (实时监控，按 Ctrl+C 退出) ==="
            tail -f "$CURRENT_LOG_DIR/application-error.log"
        else
            echo "❌ 日志文件不存在: $CURRENT_LOG_DIR/application-error.log"
        fi
        ;;
    6)
        echo ""
        echo "=== 历史日志文件 (压缩) ==="
        echo ""
        ls -lh "$CURRENT_LOG_DIR"/*.zip 2>/dev/null || echo "没有历史日志文件"
        echo ""
        read -p "输入要查看的日志文件名(或按回车返回): " logfile
        if [ -n "$logfile" ] && [ -f "$CURRENT_LOG_DIR/$logfile" ]; then
            echo ""
            echo "=== $logfile 内容 ==="
            unzip -p "$CURRENT_LOG_DIR/$logfile" | less
        fi
        ;;
    7)
        echo ""
        echo "=== 所有日志文件 ==="
        echo ""
        echo "当前月份日志:"
        ls -lh "$CURRENT_LOG_DIR/" 2>/dev/null || echo "  无日志文件"
        echo ""
        echo "历史月份:"
        ls -d logs/20*/ 2>/dev/null || echo "  无历史月份"
        ;;
    8)
        echo ""
        read -p "输入搜索关键词: " keyword
        if [ -n "$keyword" ]; then
            echo ""
            echo "=== 搜索结果: $keyword ==="
            echo ""
            echo "当前日志:"
            grep -n "$keyword" "$CURRENT_LOG_DIR/application.log" 2>/dev/null || echo "  未找到"
            echo ""
            echo "历史日志(压缩):"
            for file in "$CURRENT_LOG_DIR"/*.zip; do
                if [ -f "$file" ]; then
                    result=$(unzip -p "$file" | grep "$keyword")
                    if [ -n "$result" ]; then
                        echo "  在 $(basename $file) 中找到:"
                        echo "$result" | head -n 5
                    fi
                fi
            done
        fi
        ;;
    *)
        echo "❌ 无效选项"
        exit 1
        ;;
esac
