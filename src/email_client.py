"""IMAP 邮件客户端，负责连接邮箱、获取邮件和下载 PDF 附件。

处理 163 邮箱的特殊编码问题（gb2312/gbk），支持多种附件编码格式。

优化说明：
- 使用 UID SEARCH / UID FETCH 替代序列号命令，防止邮件删除后序列号漂移导致去重失效
- 两阶段 FETCH：先批量拉取 INTERNALDATE + BODYSTRUCTURE（几 KB），
  再只对有 PDF 附件的邮件下载完整内容，大幅减少不必要的带宽消耗
- 使用服务器 INTERNALDATE 作为时间基准，比邮件 Date 头更可靠
"""

import email
import email.header
import imaplib
import logging
import re
import ssl
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.message import Message
from typing import Dict, List, Optional, Tuple

import certifi

logger = logging.getLogger(__name__)

# 发票相关邮件主题关键词，用于辅助判断是否值得下载完整邮件
INVOICE_SUBJECT_KEYWORDS = ['发票', 'invoice', '报销', 'receipt', '电子票', '增值税']


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
    """IMAP 邮件客户端（支持 163/QQ/Gmail 等）。"""

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
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            self._conn = imaplib.IMAP4_SSL(
                self.imap_server,
                self.imap_port,
                ssl_context=ssl_context,
                timeout=self.timeout
            )
            self._conn.login(self.username, self.auth_code)
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
                if part.get_content_type() == "text/plain":
                    return self._decode_payload(part)
            for part in msg.walk():
                if part.get_content_type() == "text/html":
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
                content_type = part.get_content_type()
                if content_type != "application/pdf":
                    continue
            else:
                content_type = part.get_content_type()

            filename = part.get_filename()
            if filename:
                filename = self._decode_header_value(filename)

            if content_type == "application/pdf" or (filename and filename.lower().endswith(".pdf")):
                data = part.get_payload(decode=True)
                if data:
                    if not filename:
                        filename = "unnamed.pdf"
                    attachments.append((filename, data))
                    logger.info("提取附件: %s (%.1f KB)", filename, len(data) / 1024)

            elif content_type == "application/octet-stream" and filename:
                if filename.lower().endswith(".pdf"):
                    data = part.get_payload(decode=True)
                    if data:
                        attachments.append((filename, data))
                        logger.debug("提取附件(octet-stream): %s (%d bytes)", filename, len(data))

        return attachments

    # ------------------------------------------------------------------ #
    #  核心方法：fetch_emails（统一首次同步与后续同步入口）                   #
    # ------------------------------------------------------------------ #

    def fetch_emails(
        self,
        folder: str = "INBOX",
        max_count: int = 30,
        since_date: Optional[datetime] = None,
    ) -> Tuple[List[EmailMessage], Optional[datetime]]:
        """
        获取邮件（首次同步与后续同步的统一入口）。

        逻辑：
          - since_date 有值：搜索该日期当天 0 点之后的所有邮件，取最旧 max_count 封
                            （IMAP SINCE 只有日期粒度，同天已处理邮件靠 email_uid 去重跳过）
          - since_date 为 None：搜索近 30 天所有邮件，取最新 max_count 封
          两种情况都不过滤已读/未读。

        Args:
            folder:      邮箱文件夹（默认 INBOX）
            max_count:   本次最多处理的邮件数（默认 30）
            since_date:  上次同步游标（UTC datetime）；None 表示没有历史记录

        Returns:
            (emails, latest_internaldate)
            emails:               含 PDF 附件（或主题含发票关键词）的完整邮件列表
            latest_internaldate:  本批次所有邮件中最新的 INTERNALDATE（UTC naive datetime）
                                  无论是否有发票，都用此值更新 last_sync_date
        """
        if not self._conn:
            raise RuntimeError("未连接邮箱，请先调用 connect()")

        status, data = self._conn.select(folder)
        if status != "OK":
            logger.error("选择文件夹 '%s' 失败: %s", folder, data)
            try:
                _, folders = self._conn.list()
                logger.info("可用文件夹: %s", [f.decode() for f in (folders or [])])
            except Exception:
                pass
            return [], None

        logger.info("已选择文件夹 '%s', 邮件总数: %s", folder, data[0].decode())

        # ── Step 1: UID SEARCH ──────────────────────────────────────────
        if since_date is not None:
            # 有游标：从该日期当天 0 点开始搜（IMAP SINCE 只支持日期粒度）
            date_str = since_date.strftime("%d-%b-%Y")
            criteria = f'SINCE {date_str}'
            logger.info("有游标同步，搜索条件: %s（游标: %s）", criteria, since_date)
        else:
            # 无游标：近 30 天所有邮件
            date_str = (datetime.now() - timedelta(days=30)).strftime("%d-%b-%Y")
            criteria = f'SINCE {date_str}'
            logger.info("无游标同步，搜索条件: %s", criteria)

        status, search_data = self._conn.uid('search', None, criteria)
        if status != "OK":
            logger.warning("UID SEARCH 失败: %s，尝试搜索全部邮件", status)
            status, search_data = self._conn.uid('search', None, 'ALL')
            if status != "OK":
                logger.error("UID SEARCH 完全失败")
                return [], None

        all_uids = search_data[0].split()
        if not all_uids:
            logger.info("没有符合条件的邮件")
            return [], None

        if since_date is not None:
            # 有游标：取最旧 N 封，从游标处往后推进
            uid_list = all_uids[:max_count]
            logger.info("有游标同步: 共 %d 封候选邮件，取最旧 %d 封", len(all_uids), len(uid_list))
        else:
            # 无游标：取最新 N 封，让用户首次就能看到最近的发票
            uid_list = all_uids[-max_count:]
            logger.info("无游标同步: 共 %d 封候选邮件，取最新 %d 封", len(all_uids), len(uid_list))

        # ── Step 2: 批量拉取 INTERNALDATE + BODYSTRUCTURE（一次请求）────
        uid_str = b','.join(uid_list)
        status, phase1_data = self._conn.uid(
            'fetch', uid_str,
            '(UID INTERNALDATE BODYSTRUCTURE BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])'
        )

        if status != "OK" or not phase1_data:
            logger.warning("批量元数据获取失败，降级为逐封全量下载")
            return self._fetch_full_fallback(uid_list), None

        # 解析阶段 1 响应
        phase1_results = self._parse_phase1_response(phase1_data)

        # latest_internaldate 追踪所有邮件（含无 PDF 的）
        latest_internaldate: Optional[datetime] = None
        for uid_bytes in uid_list:
            uid = uid_bytes.decode()
            meta = phase1_results.get(uid, {})
            dt = meta.get('internaldate')
            if dt and (latest_internaldate is None or dt > latest_internaldate):
                latest_internaldate = dt

        # ── Step 3: 只为候选邮件下载完整内容 ──────────────────────────
        # 跳过条件：BODYSTRUCTURE 明确无 PDF，且主题无发票关键词
        messages = []
        for uid_bytes in uid_list:
            uid = uid_bytes.decode()
            meta = phase1_results.get(uid, {})
            has_pdf = meta.get('has_pdf', True)   # 默认 True（不确定时保守下载）
            subject = meta.get('subject', '')
            has_keyword = any(kw in subject for kw in INVOICE_SUBJECT_KEYWORDS)

            if not has_pdf and not has_keyword:
                logger.info(
                    "邮件 UID=%s 跳过（无 PDF 且主题无关键词）: %s",
                    uid, subject or "(无主题)"
                )
                continue

            try:
                status, msg_data = self._conn.uid('fetch', uid_bytes, '(BODY.PEEK[])')
                if status != "OK" or not msg_data or not msg_data[0]:
                    continue

                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                email_msg = EmailMessage(
                    uid=uid,
                    subject=self._decode_header_value(msg.get("Subject", "")),
                    sender=self._decode_header_value(msg.get("From", "")),
                    date=meta.get('internaldate_str') or msg.get("Date", ""),
                    body_text=self._extract_body(msg),
                    attachments=self._extract_attachments(msg),
                )
                messages.append(email_msg)
                logger.info("已下载邮件: UID=%s | 主题=%s | 附件=%d 个", uid, email_msg.subject or "(无主题)", len(email_msg.attachments))

            except Exception as e:
                logger.error("获取邮件 UID=%s 完整内容失败: %s", uid, e)
                continue

        logger.info(
            "本次获取完成: 候选 %d 封 → 下载 %d 封（跳过无 PDF: %d 封）",
            len(uid_list), len(messages), len(uid_list) - len(messages)
        )
        return messages, latest_internaldate

    # ------------------------------------------------------------------ #
    #  内部辅助方法                                                         #
    # ------------------------------------------------------------------ #

    def _parse_phase1_response(self, data: list) -> Dict[str, dict]:
        """
        解析批量 FETCH 阶段 1 的响应数据。

        Returns:
            {uid: {'internaldate': datetime|None, 'internaldate_str': str,
                   'has_pdf': bool, 'subject': str}}
        """
        results: Dict[str, dict] = {}

        for item in data:
            if not isinstance(item, tuple):
                continue

            meta_bytes: bytes = item[0]   # 含 UID / INTERNALDATE / BODYSTRUCTURE
            header_bytes: bytes = item[1] if len(item) > 1 else b''

            # 提取 UID
            uid_match = re.search(rb'UID\s+(\d+)', meta_bytes, re.IGNORECASE)
            if not uid_match:
                continue
            uid = uid_match.group(1).decode()

            # 提取 INTERNALDATE
            internaldate: Optional[datetime] = None
            internaldate_str = ""
            date_match = re.search(rb'INTERNALDATE\s+"([^"]+)"', meta_bytes, re.IGNORECASE)
            if date_match:
                internaldate_str = date_match.group(1).decode()
                internaldate = self._parse_internaldate(internaldate_str)

            # 检测 PDF（在 BODYSTRUCTURE 字节中查找 pdf 相关标识）
            meta_lower = meta_bytes.lower()
            has_pdf = (
                b'"pdf"' in meta_lower
                or b'application/pdf' in meta_lower
                or b'octet-stream' in meta_lower   # 部分服务器将 PDF 标注为此类型
            )

            # 解析主题
            subject = ""
            if header_bytes:
                try:
                    parsed = email.message_from_bytes(header_bytes)
                    subject = self._decode_header_value(parsed.get("Subject", ""))
                except Exception:
                    pass

            results[uid] = {
                'internaldate': internaldate,
                'internaldate_str': internaldate_str,
                'has_pdf': has_pdf,
                'subject': subject,
            }

        return results

    def _parse_internaldate(self, date_str: str) -> Optional[datetime]:
        """
        将 IMAP INTERNALDATE 字符串解析为 UTC naive datetime。
        格式示例: "19-Mar-2026 10:30:00 +0800"
        """
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(date_str)
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        except Exception:
            try:
                dt = datetime.strptime(date_str, "%d-%b-%Y %H:%M:%S %z")
                return dt.astimezone(timezone.utc).replace(tzinfo=None)
            except Exception as e:
                logger.debug("INTERNALDATE 解析失败: %s - %s", date_str, e)
                return None

    def _fetch_full_fallback(self, uid_list: List[bytes]) -> List[EmailMessage]:
        """
        批量元数据获取失败时的降级方案：逐封下载完整邮件内容。
        性能低于两阶段方案，但保证不遗漏。
        """
        logger.warning("启用降级模式：逐封全量下载 %d 封邮件", len(uid_list))
        messages = []
        for uid_bytes in uid_list:
            uid = uid_bytes.decode()
            try:
                status, msg_data = self._conn.uid('fetch', uid_bytes, '(BODY.PEEK[])')
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
            except Exception as e:
                logger.error("降级获取邮件 UID=%s 失败: %s", uid, e)
        return messages

    def mark_as_seen(self, uid: str):
        """将邮件标记为已读（保留接口，当前同步逻辑不再依赖已读状态）。"""
        if self._conn:
            try:
                self._conn.uid('store', uid.encode(), '+FLAGS', '\\Seen')
            except Exception as e:
                logger.warning("标记邮件 UID=%s 为已读失败: %s", uid, e)

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False
