#!/bin/bash

# 发票小程序后端服务管理脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="invoice-backend"
SERVICE_FILE="${SCRIPT_DIR}/${SERVICE_NAME}.service"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查是否为 root 用户
check_root() {
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}请使用 sudo 运行此脚本${NC}"
        exit 1
    fi
}

# 安装服务
install_service() {
    echo -e "${YELLOW}安装 systemd 服务...${NC}"

    # 复制服务文件
    cp "${SERVICE_FILE}" /etc/systemd/system/

    # 重新加载 systemd
    systemctl daemon-reload

    # 启用服务（开机自启）
    systemctl enable ${SERVICE_NAME}

    echo -e "${GREEN}服务安装成功！${NC}"
    echo "使用以下命令管理服务："
    echo "  启动: sudo systemctl start ${SERVICE_NAME}"
    echo "  停止: sudo systemctl stop ${SERVICE_NAME}"
    echo "  重启: sudo systemctl restart ${SERVICE_NAME}"
    echo "  状态: sudo systemctl status ${SERVICE_NAME}"
    echo "  日志: sudo journalctl -u ${SERVICE_NAME} -f"
}

# 卸载服务
uninstall_service() {
    echo -e "${YELLOW}卸载 systemd 服务...${NC}"

    # 停止服务
    systemctl stop ${SERVICE_NAME}

    # 禁用服务
    systemctl disable ${SERVICE_NAME}

    # 删除服务文件
    rm -f /etc/systemd/system/${SERVICE_NAME}.service

    # 重新加载 systemd
    systemctl daemon-reload

    echo -e "${GREEN}服务卸载成功！${NC}"
}

# 启动服务
start_service() {
    systemctl start ${SERVICE_NAME}
    echo -e "${GREEN}服务已启动${NC}"
    systemctl status ${SERVICE_NAME}
}

# 停止服务
stop_service() {
    systemctl stop ${SERVICE_NAME}
    echo -e "${GREEN}服务已停止${NC}"
}

# 重启服务
restart_service() {
    systemctl restart ${SERVICE_NAME}
    echo -e "${GREEN}服务已重启${NC}"
    systemctl status ${SERVICE_NAME}
}

# 查看状态
status_service() {
    systemctl status ${SERVICE_NAME}
}

# 查看日志
logs_service() {
    journalctl -u ${SERVICE_NAME} -f
}

# 主菜单
case "$1" in
    install)
        check_root
        install_service
        ;;
    uninstall)
        check_root
        uninstall_service
        ;;
    start)
        check_root
        start_service
        ;;
    stop)
        check_root
        stop_service
        ;;
    restart)
        check_root
        restart_service
        ;;
    status)
        status_service
        ;;
    logs)
        logs_service
        ;;
    *)
        echo "用法: $0 {install|uninstall|start|stop|restart|status|logs}"
        echo ""
        echo "命令说明："
        echo "  install   - 安装 systemd 服务"
        echo "  uninstall - 卸载 systemd 服务"
        echo "  start     - 启动服务"
        echo "  stop      - 停止服务"
        echo "  restart   - 重启服务"
        echo "  status    - 查看服务状态"
        echo "  logs      - 查看实时日志"
        exit 1
        ;;
esac

exit 0
