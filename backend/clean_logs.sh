#!/bin/bash

# 日志清理脚本 - 清理旧日志文件

SCRIPT_DIR="/data/kaipiaoxia/code/backend"
cd "$SCRIPT_DIR"

echo "==================================="
echo "发票管理系统 - 日志清理工具"
echo "==================================="
echo ""

# 检查日志目录
if [ ! -d "logs" ]; then
    echo "❌ 日志目录不存在"
    exit 1
fi

# 显示当前日志统计
echo "当前日志统计:"
echo ""
echo "月份目录:"
ls -d logs/20*/ 2>/dev/null | while read dir; do
    size=$(du -sh "$dir" | cut -f1)
    count=$(ls "$dir"/*.zip 2>/dev/null | wc -l)
    echo "  $dir - 大小: $size, 压缩文件: $count 个"
done
echo ""
echo "总大小: $(du -sh logs/ | cut -f1)"
echo ""

# 显示清理选项
echo "清理选项:"
echo "1) 清理3个月前的日志"
echo "2) 清理6个月前的日志"
echo "3) 清理指定月份的日志"
echo "4) 清空当前日志文件(保留历史)"
echo "5) 取消"
echo ""
read -p "请选择 (1-5): " choice

case $choice in
    1)
        echo ""
        echo "正在清理3个月前的日志..."
        find logs/ -type d -name "20*" -mtime +90 -exec rm -rf {} \; 2>/dev/null
        echo "✓ 清理完成"
        ;;
    2)
        echo ""
        echo "正在清理6个月前的日志..."
        find logs/ -type d -name "20*" -mtime +180 -exec rm -rf {} \; 2>/dev/null
        echo "✓ 清理完成"
        ;;
    3)
        echo ""
        read -p "输入要删除的月份 (格式: YYYY-MM): " month
        if [ -d "logs/$month" ]; then
            read -p "确认删除 logs/$month ? (y/n): " confirm
            if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
                rm -rf "logs/$month"
                echo "✓ 已删除 logs/$month"
            else
                echo "取消删除"
            fi
        else
            echo "❌ 目录不存在: logs/$month"
        fi
        ;;
    4)
        echo ""
        echo "清空当前日志文件(历史压缩文件保留)..."
        current_month=$(date +%Y-%m)
        if [ -f "logs/$current_month/application.log" ]; then
            > "logs/$current_month/application.log"
            echo "✓ 已清空 application.log"
        fi
        if [ -f "logs/$current_month/application-error.log" ]; then
            > "logs/$current_month/application-error.log"
            echo "✓ 已清空 application-error.log"
        fi
        if [ -f "logs/nohup.log" ]; then
            > "logs/nohup.log"
            echo "✓ 已清空 nohup.log"
        fi
        echo "✓ 清理完成"
        ;;
    5)
        echo "取消清理"
        exit 0
        ;;
    *)
        echo "❌ 无效选项"
        exit 1
        ;;
esac

echo ""
echo "清理后统计:"
echo "总大小: $(du -sh logs/ | cut -f1)"
