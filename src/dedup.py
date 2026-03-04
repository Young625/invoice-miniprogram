"""已处理邮件和发票的去重管理。

使用 JSON 文件持久化两类去重状态：
- 邮件 UID：避免重复处理同一封邮件
- 发票号码：避免同一张发票从不同邮件重复录入
"""

import json
import logging
import os
from typing import Set

logger = logging.getLogger(__name__)


class DedupManager:
    """去重管理器，持久化已处理的邮件 UID 和发票号码。"""

    def __init__(self, state_file: str):
        self.state_file = state_file
        self._processed_uids: Set[str] = set()
        self._processed_invoices: Set[str] = set()
        self._load()

    def _load(self):
        """从 JSON 文件加载去重状态。"""
        if not os.path.exists(self.state_file) or os.path.getsize(self.state_file) == 0:
            logger.info("去重状态文件不存在或为空，将创建新文件: %s", self.state_file)
            return
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._processed_uids = set(data.get("processed_uids", []))
            self._processed_invoices = set(data.get("processed_invoices", []))
            logger.info(
                "加载去重状态: %d 封邮件, %d 张发票",
                len(self._processed_uids),
                len(self._processed_invoices),
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.error("去重状态文件损坏，将重置: %s", e)
            self._processed_uids = set()
            self._processed_invoices = set()

    def _save(self):
        """将去重状态写入 JSON 文件。"""
        os.makedirs(os.path.dirname(self.state_file) or ".", exist_ok=True)
        data = {
            "processed_uids": sorted(self._processed_uids),
            "processed_invoices": sorted(self._processed_invoices),
        }
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def is_email_processed(self, uid: str) -> bool:
        """检查邮件 UID 是否已处理。"""
        return uid in self._processed_uids

    def mark_email_processed(self, uid: str):
        """标记邮件 UID 为已处理并持久化。"""
        self._processed_uids.add(uid)
        self._save()

    def is_invoice_processed(self, invoice_number: str) -> bool:
        """检查发票号码是否已处理。"""
        return invoice_number in self._processed_invoices

    def mark_invoice_processed(self, invoice_number: str):
        """标记发票号码为已处理并持久化。"""
        self._processed_invoices.add(invoice_number)
        self._save()

    @property
    def processed_email_count(self) -> int:
        return len(self._processed_uids)

    @property
    def processed_invoice_count(self) -> int:
        return len(self._processed_invoices)
