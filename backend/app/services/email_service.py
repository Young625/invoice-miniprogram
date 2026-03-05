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
from storage import StorageManager
from dedup import DedupManager

import logging
from typing import List, Tuple
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

    async def process_user_emails(self, user: User) -> int:
        """
        处理单个用户的邮箱（支持多邮箱）

        Args:
            user: 用户对象

        Returns:
            提取到的发票数量
        """
        if not user.email_configs or len(user.email_configs) == 0:
            logger.warning(f"用户 {user.openid} 未配置邮箱")
            return 0

        total_invoice_count = 0

        # 遍历处理所有邮箱配置
        for idx, email_config in enumerate(user.email_configs):
            logger.info(f"开始处理用户 {user.openid} 的邮箱 [{idx+1}/{len(user.email_configs)}]: {email_config.username}")

            try:
                # 创建邮件客户端
                client = EmailClient(
                    imap_server=email_config.imap_server,
                    imap_port=email_config.imap_port,
                    username=email_config.username,
                    auth_code=email_config.auth_code
                )

                invoice_count = 0

                with client:
                    # 分页处理邮件，避免遗漏
                    page_size = 50
                    total_processed = 0

                    while True:
                        # 获取未读邮件
                        emails = client.fetch_new_emails(
                            folder=email_config.folder,
                            max_count=page_size
                        )

                        if not emails:
                            logger.info(f"邮箱 {email_config.username} 没有更多新邮件")
                            break

                        logger.info(f"邮箱 {email_config.username} 本批次发现 {len(emails)} 封新邮件")
                        batch_invoice_count = 0

                        for email_msg in emails:
                            logger.info(f"处理邮件: {email_msg.subject} (UID: {email_msg.uid})")

                            # 检查是否已处理（使用邮箱+UID作为唯一标识）
                            existing = await self.db.invoices.find_one({
                                "user_id": user.openid,
                                "email_account": email_config.username,
                                "email_uid": email_msg.uid
                            })

                            if existing:
                                logger.info(f"邮件已处理，跳过: {email_msg.subject} (UID: {email_msg.uid})")
                                # 标记为已读（即使已处理过，也要标记，避免重复获取）
                                try:
                                    client.mark_as_seen(email_msg.uid)
                                except Exception as e:
                                    logger.warning(f"标记邮件为已读失败: {e}")
                                continue

                            # 发票检测
                            logger.info(f"开始检测邮件中的发票，附件数量: {len(email_msg.attachments)}")
                            invoice_pdfs = detect_invoices(
                                email_msg.subject,
                                email_msg.body_text,
                                email_msg.attachments
                            )

                            if not invoice_pdfs:
                                logger.info(f"邮件未检测到发票: {email_msg.subject}")
                                # 标记为已读（即使没有发票，也要标记）
                                try:
                                    client.mark_as_seen(email_msg.uid)
                                except Exception as e:
                                    logger.warning(f"标记邮件为已读失败: {e}")
                                continue

                            logger.info(f"检测到 {len(invoice_pdfs)} 个发票PDF")

                            # 处理每个发票 PDF
                            for filename, pdf_data in invoice_pdfs:
                                try:
                                    # 解析发票
                                    info = self.parser.parse(pdf_data)

                                    # ⭐ 添加文件哈希去重检查
                                    import hashlib
                                    pdf_hash = hashlib.md5(pdf_data).hexdigest()

                                    # 检查1：文件哈希去重（防止相同PDF重复保存）
                                    existing_by_hash = await self.db.invoices.find_one({
                                        "user_id": user.openid,
                                        "pdf_hash": pdf_hash
                                    })

                                    if existing_by_hash:
                                        logger.info(f"PDF文件已存在（哈希重复）: {pdf_hash[:8]}...")
                                        continue

                                    # 检查2：发票号码去重
                                    if info.invoice_number:
                                        existing_invoice = await self.db.invoices.find_one({
                                            "user_id": user.openid,
                                            "invoice_number": info.invoice_number
                                        })

                                        if existing_invoice:
                                            logger.info(f"发票号码重复: {info.invoice_number}")
                                            continue

                                    # ⭐ 所有检查通过后，才保存PDF文件
                                    pdf_path = self._save_pdf(user.openid, filename, pdf_data)

                                    # 处理金额字段：将空字符串转换为 None
                                    def parse_amount(value):
                                        """将金额字段转换为 float 或 None"""
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

                                    # 创建发票记录
                                    invoice = Invoice(
                                        user_id=user.openid,
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
                                        total_amount=total_amount,
                                        items=info.items,
                                        email_subject=email_msg.subject,
                                        source_type="attachment" if filename in [a[0] for a in email_msg.attachments] else "link",
                                        pdf_path=pdf_path,
                                        is_valid=info.is_valid
                                    )

                                    # 保存到数据库（添加email_uid和email_account字段）
                                    invoice_dict = invoice.model_dump(by_alias=True, exclude=["id"])
                                    invoice_dict["email_uid"] = email_msg.uid  # 添加邮件UID
                                    invoice_dict["email_account"] = email_config.username  # 添加邮箱账号
                                    invoice_dict["pdf_hash"] = pdf_hash  # ⭐ 添加PDF哈希值

                                    await self.db.invoices.insert_one(invoice_dict)

                                    batch_invoice_count += 1
                                    logger.info(f"成功提取发票: {info.invoice_number} - {info.seller_name}")

                                except Exception as e:
                                    logger.error(f"处理发票失败: {filename}, 错误: {e}", exc_info=True)
                                    continue

                            # ⭐ 处理完邮件后标记为已读
                            try:
                                client.mark_as_seen(email_msg.uid)
                                logger.debug(f"邮件已标记为已读: {email_msg.uid}")
                            except Exception as e:
                                logger.warning(f"标记邮件为已读失败: {e}")

                        invoice_count += batch_invoice_count
                        total_processed += len(emails)

                        logger.info(f"本批次处理完成: 处理 {len(emails)} 封邮件，提取 {batch_invoice_count} 张发票")

                        # 如果本批次邮件数少于 page_size，说明没有更多邮件了
                        if len(emails) < page_size:
                            logger.info(f"邮箱 {email_config.username} 所有邮件处理完成")
                            break

                        # 安全检查：避免无限循环
                        if total_processed >= 500:
                            logger.warning(f"邮箱 {email_config.username} 已处理 {total_processed} 封邮件，达到单次上限，停止处理")
                            break

                logger.info(f"邮箱 {email_config.username} 本次提取了 {invoice_count} 张发票")
                total_invoice_count += invoice_count

            except Exception as e:
                logger.error(f"处理邮箱 {email_config.username} 失败: {e}", exc_info=True)
                continue

        logger.info(f"用户 {user.openid} 所有邮箱共提取了 {total_invoice_count} 张发票")
        return total_invoice_count

    def _save_pdf(self, user_id: str, filename: str, pdf_data: bytes) -> str:
        """
        保存 PDF 文件

        Args:
            user_id: 用户 ID
            filename: 文件名
            pdf_data: PDF 二进制数据

        Returns:
            文件相对路径
        """
        from datetime import datetime
        import os

        # 创建用户目录
        base_dir = Path(settings.INVOICE_STORAGE_PATH)
        user_dir = base_dir / user_id / datetime.now().strftime("%Y/%m")
        user_dir.mkdir(parents=True, exist_ok=True)

        # 生成文件名(包含微秒以避免冲突)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        safe_filename = f"{timestamp}_{filename}"
        file_path = user_dir / safe_filename

        # 写入文件
        with open(file_path, "wb") as f:
            f.write(pdf_data)

        # 返回相对路径
        return str(file_path.relative_to(base_dir))

    async def process_all_users(self) -> dict:
        """
        处理所有配置了邮箱的用户（支持并发处理）

        Returns:
            处理结果统计
        """
        logger.info("开始处理所有用户的邮箱")

        # 查找所有配置了邮箱的用户（使用新的email_configs字段）
        cursor = self.db.users.find({"email_configs": {"$exists": True, "$ne": []}})
        users = await cursor.to_list(length=None)

        if not users:
            logger.info("没有用户配置邮箱")
            return {"total_users": 0, "total_invoices": 0}

        logger.info(f"找到 {len(users)} 个配置了邮箱的用户")

        # 并发处理用户（限制并发数为10）
        import asyncio
        semaphore = asyncio.Semaphore(10)

        async def process_with_semaphore(user_data):
            """带信号量的用户处理"""
            async with semaphore:
                try:
                    user = User(**user_data)
                    count = await self.process_user_emails(user)
                    return {"success": True, "count": count}
                except Exception as e:
                    logger.error(f"处理用户失败: {e}", exc_info=True)
                    return {"success": False, "count": 0}

        # 并发执行所有用户的处理
        results = await asyncio.gather(
            *[process_with_semaphore(user_data) for user_data in users],
            return_exceptions=True
        )

        # 统计结果
        total_invoices = 0
        success_users = 0
        failed_users = 0

        for result in results:
            if isinstance(result, dict):
                if result["success"]:
                    success_users += 1
                    total_invoices += result["count"]
                else:
                    failed_users += 1
            else:
                # 异常情况
                failed_users += 1

        result = {
            "total_users": len(users),
            "success_users": success_users,
            "failed_users": failed_users,
            "total_invoices": total_invoices
        }

        logger.info(f"邮箱处理完成: {result}")
        return result
