"""IMAP 邮件客户端，负责连接 163 邮箱、获取邮件和下载 PDF 附件。

处理 163 邮箱的特殊编码问题（gb2312/gbk），支持多种附件编码格式。
"""

import email
import email.header
import imaplib
import logging
import os
import re
import ssl
import tempfile
from dataclasses import dataclass, field
from email.message import Message
from typing import List, Optional, Tuple

import certifi

logger = logging.getLogger(__name__)


@dataclass
class EmailMessage:
    """解析后的邮件数据。"""

    uid: str
    subject: str
    sender: str
    date: str
    body_text: str = ""
    attachments: List[Tuple[str, bytes]] = field(default_factory=list)  # (文件名, 内容)


class EmailClient:
    """163 邮箱 IMAP 客户端。"""

    def __init__(self, imap_server: str, imap_port: int, username: str, auth_code: str, timeout: int = 30):
        self.imap_server = imap_server
        self.imap_port = imap_port
        self.username = username
        self.auth_code = auth_code
        self.timeout = timeout
        self._conn: Optional[imaplib.IMAP4_SSL] = None

    def connect(self):
        """建立 IMAP 连接并登录。"""
        logger.info("连接邮箱服务器 %s:%d (超时: %ds)...", self.imap_server, self.imap_port, self.timeout)
        try:
            # 创建SSL上下文，使用certifi提供的证书
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            # 设置连接超时
            self._conn = imaplib.IMAP4_SSL(
                self.imap_server,
                self.imap_port,
                ssl_context=ssl_context,
                timeout=self.timeout
            )
            self._conn.login(self.username, self.auth_code)
            # 163 邮箱要求登录后发送 IMAP ID 命令标识客户端，否则拒绝 SELECT 操作
            self._send_imap_id()
            logger.info("邮箱登录成功: %s", self.username)
        except TimeoutError as e:
            logger.error("连接邮箱服务器超时: %s:%d - %s", self.imap_server, self.imap_port, e)
            raise
        except Exception as e:
            logger.error("连接邮箱服务器失败: %s", e)
            raise

    def _send_imap_id(self):
        """发送 IMAP ID 命令（163 邮箱强制要求）。"""
        try:
            tag = self._conn._new_tag()
            cmd = tag + b' ID ("name" "InvoiceExtractor" "version" "1.0")\r\n'
            self._conn.send(cmd)
            # 读取响应（通常两行：* ID ... 和 tag OK）
            while True:
                line = self._conn.readline()
                if line.startswith(tag):
                    break
        except Exception as e:
            logger.warning("发送 IMAP ID 命令失败: %s", e)

    def disconnect(self):
        """断开 IMAP 连接。"""
        if self._conn:
            try:
                self._conn.logout()
            except Exception:
                pass
            self._conn = None
            logger.info("已断开邮箱连接")

    def _decode_header_value(self, value: str) -> str:
        """解码邮件头部值，处理各种编码（含 163 常用的 gb2312/gbk）。"""
        if not value:
            return ""
        decoded_parts = email.header.decode_header(value)
        result = []
        for part, charset in decoded_parts:
            if isinstance(part, bytes):
                # 尝试多种编码
                for enc in [charset, "utf-8", "gbk", "gb2312", "gb18030", "latin-1"]:
                    if enc:
                        try:
                            result.append(part.decode(enc))
                            break
                        except (UnicodeDecodeError, LookupError):
                            continue
                else:
                    result.append(part.decode("utf-8", errors="replace"))
            else:
                result.append(str(part))
        return "".join(result)

    def _decode_payload(self, part: Message) -> str:
        """解码邮件正文，处理各种字符编码。"""
        payload = part.get_payload(decode=True)
        if not payload:
            return ""
        charset = part.get_content_charset() or "utf-8"
        for enc in [charset, "utf-8", "gbk", "gb2312", "gb18030", "latin-1"]:
            try:
                return payload.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue
        return payload.decode("utf-8", errors="replace")

    def _extract_body(self, msg: Message) -> str:
        """提取邮件纯文本正文。"""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    return self._decode_payload(part)
                # 如果没有纯文本，尝试 HTML
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    # 简单去除 HTML 标签
                    html = self._decode_payload(part)
                    return re.sub(r"<[^>]+>", "", html)
        else:
            return self._decode_payload(msg)
        return ""

    def _extract_attachments(self, msg: Message) -> List[Tuple[str, bytes]]:
        """提取 PDF 附件，返回 (文件名, 二进制内容) 列表。"""
        attachments = []
        for part in msg.walk():
            content_disposition = str(part.get("Content-Disposition", ""))
            if "attachment" not in content_disposition and "inline" not in content_disposition:
                # 有些发票 PDF 可能作为 inline 附件
                content_type = part.get_content_type()
                if content_type != "application/pdf":
                    continue
                # 即使没有 Content-Disposition 但是 PDF 类型也提取
            else:
                content_type = part.get_content_type()

            # 只提取 PDF 文件
            filename = part.get_filename()
            if filename:
                filename = self._decode_header_value(filename)

            if content_type == "application/pdf" or (
                filename and filename.lower().endswith(".pdf")
            ):
                data = part.get_payload(decode=True)
                if data:
                    if not filename:
                        filename = "unnamed.pdf"
                    attachments.append((filename, data))
                    logger.debug("提取附件: %s (%d bytes)", filename, len(data))

            # 有些邮件把 PDF 放在 application/octet-stream 里
            elif content_type == "application/octet-stream" and filename:
                if filename.lower().endswith(".pdf"):
                    data = part.get_payload(decode=True)
                    if data:
                        attachments.append((filename, data))
                        logger.debug("提取附件(octet-stream): %s (%d bytes)", filename, len(data))

        return attachments

    def fetch_new_emails(
        self, folder: str = "INBOX", max_count: int = 50, days: int = 30
    ) -> List[EmailMessage]:
        """获取指定文件夹中的未读邮件（默认近30天）。

        Args:
            folder: 邮箱文件夹名
            max_count: 最多获取的邮件数
            days: 获取最近多少天的邮件（默认30天）

        Returns:
            解析后的邮件列表
        """
        if not self._conn:
            raise RuntimeError("未连接邮箱，请先调用 connect()")

        status, data = self._conn.select(folder)
        if status != "OK":
            logger.error("选择文件夹 '%s' 失败: %s", folder, data)
            # 尝试列出可用文件夹
            status2, folders = self._conn.list()
            if status2 == "OK":
                logger.info("可用文件夹: %s", [f.decode() for f in folders])
            return []

        logger.info("已选择文件夹 '%s', 邮件数: %s", folder, data[0].decode())

        # 计算日期范围（IMAP 日期格式：DD-Mon-YYYY，例如：01-Feb-2024）
        from datetime import datetime, timedelta
        since_date = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")

        # 搜索未读邮件且在指定日期之后
        search_criteria = f'(UNSEEN SINCE {since_date})'
        status, data = self._conn.search(None, search_criteria)
        if status != "OK":
            logger.warning("搜索邮件失败: %s，尝试只搜索未读邮件", status)
            # 如果日期搜索失败，回退到只搜索未读
            status, data = self._conn.search(None, "UNSEEN")
            if status != "OK":
                logger.warning("搜索邮件失败: %s", status)
                return []

        uid_list = data[0].split()
        if not uid_list:
            logger.info("没有新邮件")
            return []

        # 限制数量
        uid_list = uid_list[:max_count]
        logger.info("发现 %d 封新邮件（近 %d 天）", len(uid_list), days)

        messages = []
        for uid_bytes in uid_list:
            uid = uid_bytes.decode()
            try:
                status, msg_data = self._conn.fetch(uid_bytes, "(RFC822)")
                if status != "OK" or not msg_data or not msg_data[0]:
                    continue

                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                email_msg = EmailMessage(
                    uid=uid,
                    subject=self._decode_header_value(msg.get("Subject", "")),
                    sender=self._decode_header_value(msg.get("From", "")),
                    date=msg.get("Date", ""),
                    body_text=self._extract_body(msg),
                    attachments=self._extract_attachments(msg),
                )
                messages.append(email_msg)
                logger.debug("解析邮件: [%s] %s", uid, email_msg.subject)

            except Exception as e:
                logger.error("解析邮件 %s 失败: %s", uid, e)
                continue

        return messages

    def mark_as_seen(self, uid: str):
        """将邮件标记为已读。"""
        if self._conn:
            try:
                self._conn.store(uid.encode(), "+FLAGS", "\\Seen")
            except Exception as e:
                logger.warning("标记邮件 %s 为已读失败: %s", uid, e)

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False
