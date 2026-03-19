"""邮件服务：集成现有的发票提取代码"""
import sys
import os
from pathlib import Path

# 添加现有代码路径
# 从 backend/app/services/email_service.py 到 src/ 需要向上 5 级
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / 'src'))

from email_client import EmailClient
from invoice_detector import detect_invoices
from invoice_parser import InvoiceParser

import logging
import re
import time
from datetime import datetime
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..models.user import User, EmailConfig
from ..models.invoice import Invoice
from ..core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """邮件服务：处理邮箱轮询和发票提取"""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.parser = InvoiceParser()

    # ------------------------------------------------------------------ #
    #  公开方法                                                             #
    # ------------------------------------------------------------------ #

    async def process_user_emails(self, user: User) -> dict:
        """
        处理单个用户的所有邮箱。

        Returns:
            {"success_count": int, "duplicate_count": int, "duplicate_invoices": list}
        """
        start_time = time.time()
        logger.info("=" * 60)
        logger.info("[同步开始] 用户: %s | 邮箱数: %d", user.openid, len(user.email_configs or []))

        if not user.email_configs:
            logger.warning("[同步跳过] 用户 %s 未配置任何邮箱", user.openid)
            return {"success_count": 0, "duplicate_count": 0, "duplicate_invoices": []}

        total_invoice_count = 0
        total_duplicate_count = 0
        duplicate_invoices = []

        for idx, email_config in enumerate(user.email_configs):
            logger.info("-" * 50)
            logger.info(
                "[邮箱 %d/%d] 开始处理: %s",
                idx + 1, len(user.email_configs), email_config.username
            )
            try:
                inv, dup, dup_list = await self._process_single_mailbox(user, idx, email_config)
                total_invoice_count += inv
                total_duplicate_count += dup
                duplicate_invoices.extend(dup_list)
                logger.info(
                    "[邮箱 %d/%d] 完成: %s | 新增 %d 张 | 重复 %d 张",
                    idx + 1, len(user.email_configs), email_config.username, inv, dup
                )
            except Exception as e:
                logger.error(
                    "[邮箱 %d/%d] 处理失败: %s | 错误: %s",
                    idx + 1, len(user.email_configs), email_config.username, e,
                    exc_info=True
                )
                continue

        elapsed = time.time() - start_time
        logger.info("-" * 50)
        logger.info(
            "[同步完成] 用户: %s | 新增发票: %d 张 | 跳过重复: %d 张 | 耗时: %.2f 秒",
            user.openid, total_invoice_count, total_duplicate_count, elapsed
        )
        logger.info("=" * 60)
        return {
            "success_count": total_invoice_count,
            "duplicate_count": total_duplicate_count,
            "duplicate_invoices": duplicate_invoices,
        }

    async def process_all_users(self) -> dict:
        """
        处理所有开启自动同步用户的邮箱（并发，最多 10 个用户同时处理）。
        """
        logger.info("开始处理所有用户的邮箱")

        cursor = self.db.users.find({
            "email_configs": {"$exists": True, "$ne": []},
            "auto_sync_enabled": True,
        })
        users = await cursor.to_list(length=None)

        if not users:
            logger.info("没有用户配置邮箱或开启自动同步")
            return {"total_users": 0, "total_invoices": 0}

        logger.info("找到 %d 个需要自动同步的用户", len(users))

        import asyncio
        semaphore = asyncio.Semaphore(10)

        async def process_with_semaphore(user_data):
            async with semaphore:
                try:
                    user = User(**user_data)
                    result = await self.process_user_emails(user)
                    return {"success": True, "invoice_result": result}
                except Exception as e:
                    logger.error("处理用户失败: %s", e, exc_info=True)
                    return {"success": False, "invoice_result": {"success_count": 0, "duplicate_count": 0, "duplicate_invoices": []}}

        results = await asyncio.gather(
            *[process_with_semaphore(u) for u in users],
            return_exceptions=True
        )

        total_invoices = total_duplicates = success_users = failed_users = 0
        for result in results:
            if isinstance(result, dict) and result["success"]:
                success_users += 1
                total_invoices += result["invoice_result"]["success_count"]
                total_duplicates += result["invoice_result"]["duplicate_count"]
            else:
                failed_users += 1

        summary = {
            "total_users": len(users),
            "success_users": success_users,
            "failed_users": failed_users,
            "total_invoices": total_invoices,
            "total_duplicates": total_duplicates,
        }
        logger.info("邮箱处理完成: %s", summary)
        return summary

    # ------------------------------------------------------------------ #
    #  内部方法                                                             #
    # ------------------------------------------------------------------ #

    async def _get_since_date(
        self,
        user_openid: str,
        email_config: EmailConfig,
        config_idx: int,
    ) -> Optional[datetime]:
        """
        确定本次同步的起始日期（游标）。

        策略：
        1. EmailConfig.last_sync_date 有值 → 直接使用（后续同步）
        2. 无值但库中有该邮箱的存量发票 → 用最新发票 created_at 初始化游标，走后续同步
        3. 无值且无存量发票 → 返回 None，走首次同步（近 30 天最新 30 封）
        """
        if email_config.last_sync_date:
            return email_config.last_sync_date

        # 查询该邮箱账号最新一条发票记录（用 created_at 估算上次同步位置）
        latest_invoice = await self.db.invoices.find_one(
            {"user_id": user_openid, "email_account": email_config.username},
            sort=[("created_at", -1)],
        )

        if latest_invoice and latest_invoice.get("created_at"):
            initial_date = latest_invoice["created_at"]
            # 持久化到 email_configs，后续直接使用
            await self.db.users.update_one(
                {"openid": user_openid},
                {"$set": {f"email_configs.{config_idx}.last_sync_date": initial_date}},
            )
            logger.info(
                "邮箱 %s 根据存量发票初始化游标: %s",
                email_config.username, initial_date
            )
            return initial_date

        # 真正的首次同步
        logger.info("邮箱 %s 无存量数据，执行首次同步", email_config.username)
        return None

    async def _update_last_sync_date(
        self,
        user_openid: str,
        config_idx: int,
        current_last_sync_date: Optional[datetime],
        latest_internaldate: datetime,
    ) -> None:
        """将 last_sync_date 推进到 latest_internaldate（只前进，不后退）。"""
        if current_last_sync_date and latest_internaldate <= current_last_sync_date:
            return
        await self.db.users.update_one(
            {"openid": user_openid},
            {"$set": {f"email_configs.{config_idx}.last_sync_date": latest_internaldate}},
        )
        logger.info("更新游标 email_configs[%d].last_sync_date = %s", config_idx, latest_internaldate)

    async def _process_single_mailbox(
        self,
        user: User,
        idx: int,
        email_config: EmailConfig,
    ):
        """
        处理单个邮箱，返回 (invoice_count, duplicate_count, duplicate_invoices)。
        """
        start_time = time.time()

        # 确定同步起始日期
        since_date = await self._get_since_date(user.openid, email_config, idx)
        if since_date:
            logger.info("[%s] 游标模式: 从 %s 开始检索", email_config.username, since_date.strftime("%Y-%m-%d %H:%M:%S"))
        else:
            logger.info("[%s] 首次同步: 检索近 30 天邮件", email_config.username)

        client = EmailClient(
            imap_server=email_config.imap_server,
            imap_port=email_config.imap_port,
            username=email_config.username,
            auth_code=email_config.auth_code,
        )

        invoice_count = 0
        duplicate_count = 0
        duplicate_invoices = []

        with client:
            logger.info("[%s] 正在连接 IMAP 服务器 %s:%d ...", email_config.username, email_config.imap_server, email_config.imap_port)

            emails, latest_internaldate = client.fetch_emails(
                folder=email_config.folder,
                max_count=30,
                since_date=since_date,
            )

            fetch_elapsed = time.time() - start_time
            logger.info(
                "[%s] 拉取完成: 获得 %d 封候选邮件 | 耗时 %.2f 秒",
                email_config.username, len(emails), fetch_elapsed
            )

            # 无论本批有没有发票，只要有邮件就推进游标
            if latest_internaldate:
                await self._update_last_sync_date(
                    user.openid, idx, email_config.last_sync_date, latest_internaldate
                )

            if not emails:
                logger.info("[%s] 本次搜索范围内无需处理的邮件（无新邮件或全部已过滤）", email_config.username)
                return invoice_count, duplicate_count, duplicate_invoices

            logger.info("[%s] 开始逐封检查，共 %d 封 >>>", email_config.username, len(emails))

            skipped_uid = 0  # uid 去重跳过数
            skipped_no_invoice = 0  # 无发票跳过数

            for email_idx, email_msg in enumerate(emails, 1):
                logger.info(
                    "[%s] 检查邮件 [%d/%d]: 主题=%s | UID=%s",
                    email_config.username, email_idx, len(emails), email_msg.subject or "(无主题)", email_msg.uid
                )

                # ── 邮件级去重（查 processed_emails 集合）────────────
                already_processed = await self.db.processed_emails.find_one({
                    "user_id": user.openid,
                    "email_account": email_config.username,
                    "email_uid": email_msg.uid,
                })
                if already_processed:
                    logger.info(
                        "[%s]   → 该邮件已处理过，跳过 (UID=%s)",
                        email_config.username, email_msg.uid
                    )
                    skipped_uid += 1
                    continue

                # ── 发票检测 ──────────────────────────────────────────
                logger.info("[%s]   → 检测发票中（附件数: %d）...", email_config.username, len(email_msg.attachments))
                invoice_pdfs = detect_invoices(
                    email_msg.subject,
                    email_msg.body_text,
                    email_msg.attachments,
                )
                if not invoice_pdfs:
                    logger.info("[%s]   → 未检测到发票，标记已读并记录", email_config.username)
                    skipped_no_invoice += 1
                    try:
                        client.mark_as_seen(email_msg.uid)
                    except Exception:
                        pass
                    # 记录到 processed_emails，避免下次重复扫描
                    try:
                        await self.db.processed_emails.insert_one({
                            "user_id": user.openid,
                            "email_account": email_config.username,
                            "email_uid": email_msg.uid,
                            "processed_at": datetime.utcnow(),
                            "had_invoice": False,
                        })
                    except Exception:
                        pass  # 唯一索引冲突可忽略
                    continue

                logger.info(
                    "[%s]   → 检测到 %d 个发票 PDF: %s",
                    email_config.username, len(invoice_pdfs),
                    ", ".join(f[0] for f in invoice_pdfs)
                )

                # 同一封邮件内按 PDF 内容去重（附件和正文链接可能是同一份文件）
                import hashlib
                seen_hashes: set = set()
                unique_pdfs = []
                for fname, fdata in invoice_pdfs:
                    h = hashlib.md5(fdata).hexdigest()
                    if h not in seen_hashes:
                        seen_hashes.add(h)
                        unique_pdfs.append((fname, fdata))
                    else:
                        logger.info(
                            "[%s]     邮件内重复 PDF 已去重（附件与链接内容相同）: %s",
                            email_config.username, fname
                        )
                invoice_pdfs = unique_pdfs

                # ── 处理每个发票 PDF ──────────────────────────────────
                for filename, pdf_data in invoice_pdfs:
                    logger.info("[%s]     处理 PDF: %s (%.1f KB)", email_config.username, filename, len(pdf_data) / 1024)
                    try:
                        inv, dup, dup_info = await self._process_single_pdf(
                            user.openid, email_config.username, email_msg, filename, pdf_data
                        )
                        invoice_count += inv
                        duplicate_count += dup
                        if dup_info:
                            duplicate_invoices.append(dup_info)
                            logger.info("[%s]     重复发票: %s | 原因: %s", email_config.username, dup_info.get("invoice_number"), dup_info.get("reason"))
                    except Exception as e:
                        logger.error(
                            "[%s]     处理 PDF 失败: %s | 错误: %s",
                            email_config.username, filename, e, exc_info=True
                        )
                        continue

                # 标记为已读
                try:
                    client.mark_as_seen(email_msg.uid)
                    logger.info("[%s]   → 邮件已标记为已读 (UID=%s)", email_config.username, email_msg.uid)
                except Exception as e:
                    logger.warning("[%s]   → 标记已读失败: %s", email_config.username, e)

                # 记录到 processed_emails，无论发票是新增还是重复，都不再重复扫描
                try:
                    await self.db.processed_emails.insert_one({
                        "user_id": user.openid,
                        "email_account": email_config.username,
                        "email_uid": email_msg.uid,
                        "processed_at": datetime.utcnow(),
                        "had_invoice": True,
                    })
                except Exception:
                    pass  # 唯一索引冲突可忽略

            # 本次扫描汇总
            logger.info(
                "[%s] <<< 扫描结束 | 共检查 %d 封 | 新增发票 %d 张 | 重复 %d 张 | 无发票跳过 %d 封 | 已处理过跳过 %d 封",
                email_config.username, len(emails),
                invoice_count, duplicate_count, skipped_no_invoice, skipped_uid
            )
            if invoice_count == 0 and duplicate_count == 0:
                logger.info("[%s] 本次同步未发现新发票", email_config.username)

        total_elapsed = time.time() - start_time
        logger.info(
            "[%s] 邮箱处理完成 | 新增: %d 张 | 重复: %d 张 | 总耗时: %.2f 秒",
            email_config.username, invoice_count, duplicate_count, total_elapsed
        )
        return invoice_count, duplicate_count, duplicate_invoices

    async def _process_single_pdf(
        self,
        user_openid: str,
        email_account: str,
        email_msg,
        filename: str,
        pdf_data: bytes,
    ):
        """
        处理单个发票 PDF，返回 (success_count, duplicate_count, dup_info_or_None)。
        """
        import hashlib

        # 解析发票
        logger.info("[%s]     正在解析发票: %s", email_account, filename)
        info = self.parser.parse(pdf_data)
        logger.info(
            "[%s]     解析结果: 发票号=%s | 卖方=%s | 金额=%s",
            email_account,
            info.invoice_number or "未识别",
            info.seller_name or "未识别",
            info.total_amount or "未识别"
        )

        # ── PDF 哈希去重 ──────────────────────────────────────────────
        pdf_hash = hashlib.md5(pdf_data).hexdigest()
        if await self.db.invoices.find_one({"user_id": user_openid, "pdf_hash": pdf_hash}):
            logger.info("PDF 文件重复（哈希: %s...）", pdf_hash[:8])
            return 0, 1, {
                "invoice_number": info.invoice_number or "未识别",
                "seller_name": info.seller_name or "未识别",
                "reason": "PDF文件重复",
            }

        # ── 发票号全局去重 ────────────────────────────────────────────
        if info.invoice_number:
            existing = await self.db.invoices.find_one({"invoice_number": info.invoice_number})
            if existing:
                existing_user = existing.get("user_id")
                reason = "您已添加过此发票" if existing_user == user_openid else "此发票已被其他用户添加"
                logger.info("发票号重复 (%s): %s", reason, info.invoice_number)
                return 0, 1, {
                    "invoice_number": info.invoice_number,
                    "seller_name": info.seller_name or "未识别",
                    "reason": reason,
                }

        # ── 保存 PDF ─────────────────────────────────────────────────
        pdf_path = self._save_pdf(user_openid, filename, pdf_data)

        # ── 金额字段处理 ──────────────────────────────────────────────
        def parse_amount(value):
            if value is None or value == '':
                return None
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                try:
                    return float(value.strip())
                except (ValueError, TypeError):
                    return None
            return None

        amount = parse_amount(info.amount)
        tax_amount = parse_amount(info.tax_amount)
        total_amount = parse_amount(info.total_amount)

        # ── 项目名称提取 ──────────────────────────────────────────────
        FIXED_PROJECTS = [
            '餐饮服务', '运输服务', '住宿服务', '办公用品',
            '金融服务', '通讯服务', '会议服务', '培训服务',
            '咨询服务', '租赁服务', '维修服务',
        ]
        project_name = '其他'
        if info.items:
            first_item = (info.items[0] or '').strip()
            if first_item:
                match = re.search(r'\*([^*]+)\*', first_item)
                extracted = match.group(1).strip() if match else first_item
                if extracted in FIXED_PROJECTS:
                    project_name = extracted

        # ── 写入数据库 ────────────────────────────────────────────────
        invoice = Invoice(
            user_id=user_openid,
            invoice_type=info.invoice_type,
            invoice_code=info.invoice_code,
            invoice_number=info.invoice_number,
            invoice_date=info.invoice_date,
            buyer_name=info.buyer_name,
            buyer_tax_id=info.buyer_tax_id,
            seller_name=info.seller_name,
            seller_tax_id=info.seller_tax_id,
            amount=amount,
            tax_amount=tax_amount,
            tax_rate=float(info.tax_rate) if info.tax_rate else None,
            total_amount=total_amount,
            items=info.items,
            project_name=project_name,
            email_subject=email_msg.subject,
            source_type="attachment" if filename in [a[0] for a in email_msg.attachments] else "link",
            pdf_path=pdf_path,
            is_valid=info.is_valid,
        )

        invoice_dict = invoice.model_dump(by_alias=True, exclude=["id"])
        invoice_dict["email_uid"] = email_msg.uid
        invoice_dict["email_account"] = email_account
        invoice_dict["pdf_hash"] = pdf_hash

        try:
            await self.db.invoices.insert_one(invoice_dict)
            logger.info("成功提取发票: %s - %s", info.invoice_number, info.seller_name)
            return 1, 0, None
        except Exception as insert_err:
            err_str = str(insert_err)
            if "duplicate key error" in err_str.lower() or "E11000" in err_str:
                logger.warning("发票 %s 插入冲突（数据库唯一索引）", info.invoice_number)
                return 0, 1, {
                    "invoice_number": info.invoice_number or "未识别",
                    "seller_name": info.seller_name or "未识别",
                    "reason": "此发票已被其他用户添加",
                }
            logger.error("插入发票失败: %s, 错误: %s", info.invoice_number, insert_err, exc_info=True)
            raise

    def _save_pdf(self, user_id: str, filename: str, pdf_data: bytes) -> str:
        """保存 PDF 文件，返回相对路径。"""
        base_dir = Path(settings.INVOICE_STORAGE_PATH)
        user_dir = base_dir / user_id / datetime.now().strftime("%Y/%m")
        user_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        safe_filename = f"{timestamp}_{filename}"
        file_path = user_dir / safe_filename

        with open(file_path, "wb") as f:
            f.write(pdf_data)

        return str(file_path.relative_to(base_dir))
