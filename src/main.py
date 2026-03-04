"""发票自动提取守护进程入口。

主循环：每隔指定间隔轮询邮箱，检测并提取发票，保存 PDF 和更新 Excel 汇总表。
每次轮询独立建立/断开 IMAP 连接，避免 163 邮箱长连接不稳定问题。
"""

import logging
import logging.handlers
import os
import signal
import sys
import time
from pathlib import Path

import yaml

from .dedup import DedupManager
from .email_client import EmailClient
from .invoice_detector import detect_invoices
from .invoice_parser import InvoiceParser
from .storage import StorageManager

logger = logging.getLogger("invoice_extractor")


def load_config(config_path: str) -> dict:
    """加载 YAML 配置文件。"""
    if not os.path.exists(config_path):
        print(f"错误: 配置文件不存在: {config_path}")
        print("请复制 config/config.yaml.example 为 config/config.yaml 并填入实际配置")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def setup_logging(config: dict, project_root: str):
    """配置日志系统。"""
    log_config = config.get("logging", {})
    log_level = getattr(logging, log_config.get("level", "INFO").upper(), logging.INFO)
    log_file = os.path.join(project_root, log_config.get("file", "logs/invoice_extractor.log"))
    max_bytes = log_config.get("max_bytes", 10 * 1024 * 1024)
    backup_count = log_config.get("backup_count", 5)

    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    # 根 logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 文件 handler（轮转）
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    file_handler.setLevel(log_level)
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)

    # 控制台 handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    console_handler.setFormatter(console_formatter)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


class InvoiceExtractorDaemon:
    """发票自动提取守护进程。"""

    def __init__(self, config: dict, project_root: str):
        self.config = config
        self.project_root = project_root
        self._running = True

        # 初始化组件
        email_cfg = config["email"]
        self.email_config = email_cfg
        self.folder = email_cfg.get("folder", "INBOX")

        polling_cfg = config.get("polling", {})
        self.poll_interval = polling_cfg.get("interval", 300)
        self.max_emails = polling_cfg.get("max_emails_per_poll", 50)

        storage_cfg = config.get("storage", {})
        invoice_dir = os.path.join(
            project_root, storage_cfg.get("invoice_dir", "data/invoices")
        )
        excel_path = os.path.join(
            project_root, storage_cfg.get("excel_path", "data/output/发票汇总.xlsx")
        )

        dedup_cfg = config.get("dedup", {})
        state_file = os.path.join(
            project_root, dedup_cfg.get("state_file", "processed_emails.json")
        )

        self.parser = InvoiceParser()
        self.storage = StorageManager(invoice_dir, excel_path)
        self.dedup = DedupManager(state_file)

        # 信号处理
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """优雅关闭。"""
        sig_name = signal.Signals(signum).name
        logger.info("收到信号 %s，准备退出...", sig_name)
        self._running = False

    def _process_single_poll(self):
        """执行一次邮箱轮询。"""
        email_cfg = self.email_config
        client = EmailClient(
            imap_server=email_cfg["imap_server"],
            imap_port=email_cfg.get("imap_port", 993),
            username=email_cfg["username"],
            auth_code=email_cfg["auth_code"],
        )

        try:
            with client:
                emails = client.fetch_new_emails(
                    folder=self.folder, max_count=self.max_emails
                )

                if not emails:
                    return

                invoice_count = 0
                for email_msg in emails:
                    # 邮件级去重
                    if self.dedup.is_email_processed(email_msg.uid):
                        logger.debug("跳过已处理邮件: [%s] %s", email_msg.uid, email_msg.subject)
                        continue

                    # 发票检测
                    invoice_pdfs = detect_invoices(
                        email_msg.subject,
                        email_msg.body_text,
                        email_msg.attachments,
                    )

                    if not invoice_pdfs:
                        # 非发票邮件也标记为已处理
                        self.dedup.mark_email_processed(email_msg.uid)
                        continue

                    # 处理每个发票 PDF
                    for filename, pdf_data in invoice_pdfs:
                        # 解析发票
                        info = self.parser.parse(pdf_data)

                        if not info.is_valid:
                            logger.warning(
                                "发票解析不完整，仍保存: %s (号码=%s, 金额=%s)",
                                filename,
                                info.invoice_number or "未知",
                                info.total_amount or "未知",
                            )

                        # 发票号码去重
                        if info.invoice_number and self.dedup.is_invoice_processed(
                            info.invoice_number
                        ):
                            logger.info(
                                "跳过重复发票: %s (号码=%s)",
                                filename,
                                info.invoice_number,
                            )
                            continue

                        # 保存 PDF
                        pdf_rel_path = self.storage.save_pdf(
                            pdf_data, info, filename
                        )

                        # 更新 Excel
                        self.storage.append_to_excel(
                            info, email_msg.subject, pdf_rel_path
                        )

                        # 标记发票为已处理
                        if info.invoice_number:
                            self.dedup.mark_invoice_processed(info.invoice_number)

                        invoice_count += 1

                    # 标记邮件为已处理
                    self.dedup.mark_email_processed(email_msg.uid)

                if invoice_count > 0:
                    logger.info(
                        "本次轮询处理完成: %d 封邮件, %d 张发票",
                        len(emails),
                        invoice_count,
                    )

        except Exception as e:
            logger.error("轮询出错: %s", e, exc_info=True)

    def run(self):
        """启动守护进程主循环。"""
        logger.info("=" * 60)
        logger.info("发票自动提取服务启动")
        logger.info("邮箱: %s", self.email_config["username"])
        logger.info("轮询间隔: %d 秒", self.poll_interval)
        logger.info(
            "已处理: %d 封邮件, %d 张发票",
            self.dedup.processed_email_count,
            self.dedup.processed_invoice_count,
        )
        logger.info("=" * 60)

        while self._running:
            logger.info("开始轮询邮箱...")
            self._process_single_poll()

            if not self._running:
                break

            logger.info("等待 %d 秒后下次轮询...", self.poll_interval)
            # 分段 sleep，便于响应信号
            for _ in range(self.poll_interval):
                if not self._running:
                    break
                time.sleep(1)

        logger.info("发票自动提取服务已停止")

    def run_once(self):
        """执行单次轮询（用于测试）。"""
        logger.info("执行单次轮询...")
        self._process_single_poll()
        logger.info("单次轮询完成")


def main():
    """程序入口。"""
    # 确定项目根目录
    project_root = str(Path(__file__).resolve().parent.parent)

    # 加载配置
    config_path = os.path.join(project_root, "config", "config.yaml")
    config = load_config(config_path)

    # 设置日志
    setup_logging(config, project_root)

    # 解析命令行参数
    run_once = "--once" in sys.argv

    # 启动守护进程
    daemon = InvoiceExtractorDaemon(config, project_root)

    if run_once:
        daemon.run_once()
    else:
        daemon.run()


if __name__ == "__main__":
    main()
