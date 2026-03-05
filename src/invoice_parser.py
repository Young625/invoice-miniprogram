"""发票 PDF 解析模块：提取发票的结构化信息。

支持两种发票格式：
- 传统增值税电子发票：发票代码(10-12位) + 发票号码(8位)
- 数电发票（全电发票）：无发票代码 + 发票号码(20位)

使用 pdfplumber 提取文本和表格，正则匹配关键字段。
"""

import io
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

import pdfplumber

logger = logging.getLogger(__name__)


@dataclass
class InvoiceInfo:
    """解析后的发票信息。"""

    # 基本信息
    invoice_type: str = ""       # 发票类型（增值税电子普通发票/数电发票等）
    invoice_code: str = ""       # 发票代码（数电发票为空）
    invoice_number: str = ""     # 发票号码
    invoice_date: str = ""       # 开票日期

    # 购买方信息
    buyer_name: str = ""         # 购买方名称
    buyer_tax_id: str = ""       # 购买方纳税人识别号

    # 销售方信息
    seller_name: str = ""        # 销售方名称
    seller_tax_id: str = ""      # 销售方纳税人识别号

    # 金额信息
    amount: str = ""             # 金额（不含税）
    tax_amount: str = ""         # 税额
    total_amount: str = ""       # 价税合计

    # 商品信息
    items: List[str] = field(default_factory=list)  # 商品/服务名称列表

    @property
    def is_valid(self) -> bool:
        """发票信息是否足够完整。"""
        return bool(self.invoice_number and self.total_amount)

    @property
    def is_digital_invoice(self) -> bool:
        """是否为数电发票（全电发票）。"""
        return len(self.invoice_number) == 20


class InvoiceParser:
    """发票 PDF 解析器。"""

    # 发票类型识别模式
    TYPE_PATTERNS = [
        (r"增值税电子专用发票", "增值税电子专用发票"),
        (r"增值税电子普通发票", "增值税电子普通发票"),
        (r"增值税专用发票", "增值税专用发票"),
        (r"增值税普通发票", "增值税普通发票"),
        (r"电子发票[（(]增值税专用发票[）)]", "数电发票(专用)"),
        (r"电子发票[（(]普通[）)]", "数电发票(普通)"),
        (r"数电发票", "数电发票"),
        (r"全电发票", "数电发票"),
        (r"电子发票", "电子发票"),
    ]

    # 发票代码模式：10-12位数字
    CODE_PATTERN = re.compile(
        r"发票代码[：:\s]*(\d{10,12})"
    )

    # 发票号码模式：8位（传统）或20位（数电）
    NUMBER_PATTERNS = [
        re.compile(r"发票号码[：:\s]*(\d{20})"),   # 数电发票优先匹配
        re.compile(r"发票号码[：:\s]*(\d{8})"),     # 传统发票
        re.compile(r"No[.．：:\s]*(\d{20})"),       # 英文标识
        re.compile(r"No[.．：:\s]*(\d{8})"),
    ]

    # 开票日期模式
    DATE_PATTERNS = [
        # 匹配各种"年月日"格式，使用 .? 来匹配任何可能的"月"和"日"字符变体
        re.compile(r"开票日期[：:\s]*(\d{4})\s*年\s*(\d{1,2})\s*.?\s*(\d{1,2})\s*.?"),
        # 匹配 2024-01-15 格式
        re.compile(r"开票日期[：:\s]*(\d{4})[-./ ](\d{1,2})[-./ ](\d{1,2})"),
    ]

    # 纳税人识别号模式：15-20位数字字母
    TAX_ID_PATTERN = re.compile(
        r"纳税人识别号[：:\s]*([A-Za-z0-9]{15,20})"
    )

    # 统一社会信用代码也可作为税号
    CREDIT_CODE_PATTERN = re.compile(
        r"统一社会信用代码[/：:\s]*\n*\s*纳税人识别号[：:\s]*([A-Za-z0-9]{15,20})"
    )

    # "合 计" 行同时提取金额和税额：合 计 ¥192.08 ¥1.92
    SUBTOTAL_LINE_PATTERN = re.compile(
        r"合\s*计\s*[¥￥]\s*([\d,]+\.\d{2})\s*[¥￥]\s*([\d,]+\.\d{2})"
    )

    # 价税合计
    TOTAL_PATTERNS = [
        re.compile(r"价税合计[（(]大写[）)][^¥￥]*[¥￥]\s*([\d,]+\.\d{2})"),
        re.compile(r"价税合计[^¥￥]*?[¥￥]\s*([\d,]+\.\d{2})"),
        re.compile(r"价税合计.*?(\d[\d,]*\.\d{2})"),
        re.compile(r"[（(]小写[）)]\s*[¥￥]\s*([\d,]+\.\d{2})"),
    ]

    # 购买方/销售方名称模式
    NAME_PATTERN = re.compile(r"名\s*称[：:\s]*(.+?)(?:\n|$)")

    def parse(self, pdf_data: bytes) -> InvoiceInfo:
        """解析发票 PDF，提取结构化信息。

        Args:
            pdf_data: PDF 文件二进制内容

        Returns:
            解析后的发票信息
        """
        info = InvoiceInfo()

        try:
            with pdfplumber.open(io.BytesIO(pdf_data)) as pdf:
                full_text = ""
                tables = []
                for page in pdf.pages[:3]:
                    page_text = page.extract_text() or ""
                    full_text += page_text + "\n"
                    page_tables = page.extract_tables() or []
                    tables.extend(page_tables)

            if not full_text.strip():
                logger.warning("PDF 无法提取文本")
                return info

            self._parse_type(full_text, info)
            self._parse_code_and_number(full_text, info)
            self._parse_date(full_text, info)
            self._parse_buyer_seller(full_text, tables, info)
            self._parse_amounts(full_text, info)
            self._parse_items(full_text, tables, info)

            logger.info(
                "发票解析完成: 类型=%s, 号码=%s, 金额=%s, 购买方=%s, 销售方=%s",
                info.invoice_type,
                info.invoice_number,
                info.total_amount,
                info.buyer_name,
                info.seller_name,
            )

        except Exception as e:
            logger.error("解析发票 PDF 失败: %s", e)

        return info

    def _parse_type(self, text: str, info: InvoiceInfo):
        """识别发票类型。"""
        for pattern, type_name in self.TYPE_PATTERNS:
            if re.search(pattern, text):
                info.invoice_type = type_name
                return
        info.invoice_type = "未知类型"

    def _parse_code_and_number(self, text: str, info: InvoiceInfo):
        """提取发票代码和号码。"""
        # 发票代码
        match = self.CODE_PATTERN.search(text)
        if match:
            info.invoice_code = match.group(1)

        # 发票号码
        for pattern in self.NUMBER_PATTERNS:
            match = pattern.search(text)
            if match:
                info.invoice_number = match.group(1)
                break

    def _parse_date(self, text: str, info: InvoiceInfo):
        """提取开票日期。"""
        for pattern in self.DATE_PATTERNS:
            match = pattern.search(text)
            if match:
                year, month, day = match.group(1), match.group(2), match.group(3)
                info.invoice_date = f"{year}-{int(month):02d}-{int(day):02d}"
                return

    def _parse_buyer_seller(self, text: str, tables: list, info: InvoiceInfo):
        """提取购买方和销售方信息。

        优先从表格中提取（数电发票的表格结构更可靠），
        回退到纯文本正则匹配。
        """
        # 策略1：从表格提取（数电发票常见格式）
        if self._parse_buyer_seller_from_tables(tables, info):
            return

        # 策略2：纯文本正则匹配
        self._parse_buyer_seller_from_text(text, info)

    def _parse_buyer_seller_from_tables(self, tables: list, info: InvoiceInfo) -> bool:
        """从表格中提取购买方/销售方信息。"""
        found = False
        for table in tables:
            if not table:
                continue
            for row in table:
                if not row:
                    continue
                for cell in row:
                    if not cell:
                        continue
                    cell_str = str(cell)
                    # 数电发票格式："名称：浙江大学\n统一社会信用代码/纳税人识别号：xxx"
                    # 判断是购买方还是销售方所在单元格
                    is_buyer_cell = any(k in str(r or "") for r in row for k in ["购", "买方"])
                    is_seller_cell = any(k in str(r or "") for r in row for k in ["销", "售方"])

                    name_match = re.search(r"名称[：:]\s*(.+?)(?:\n|$)", cell_str)
                    tax_match = re.search(
                        r"(?:统一社会信用代码|纳税人识别号)[/：:\s]*(?:纳税人识别号[：:\s]*)?([A-Za-z0-9]{15,20})",
                        cell_str,
                    )

                    if name_match:
                        name = name_match.group(1).strip()
                        if is_buyer_cell and not info.buyer_name:
                            info.buyer_name = name
                            found = True
                        elif is_seller_cell and not info.seller_name:
                            info.seller_name = name
                            found = True

                    if tax_match:
                        tax_id = tax_match.group(1)
                        if is_buyer_cell and not info.buyer_tax_id:
                            info.buyer_tax_id = tax_id
                            found = True
                        elif is_seller_cell and not info.seller_tax_id:
                            info.seller_tax_id = tax_id
                            found = True

        return found

    def _parse_buyer_seller_from_text(self, text: str, info: InvoiceInfo):
        """从纯文本中提取购买方/销售方信息（传统发票格式）。"""
        # 数电发票文本格式："购 名称：xxx 销 名称：yyy"
        # 先尝试单行内同时出现购/销的格式
        line_pattern = re.compile(
            r"购\s*名称[：:]\s*(.+?)\s+销\s*名称[：:]\s*(.+?)$", re.MULTILINE
        )
        match = line_pattern.search(text)
        if match:
            if not info.buyer_name:
                info.buyer_name = match.group(1).strip()
            if not info.seller_name:
                info.seller_name = match.group(2).strip()

        # 传统发票格式
        buyer_pos = -1
        seller_pos = -1
        for keyword in ["购买方", "购 买 方", "购方"]:
            pos = text.find(keyword)
            if pos != -1:
                buyer_pos = pos
                break
        for keyword in ["销售方", "销 售 方", "销方"]:
            pos = text.find(keyword)
            if pos != -1:
                seller_pos = pos
                break

        if buyer_pos != -1 and not info.buyer_name:
            end_pos = seller_pos if seller_pos > buyer_pos else buyer_pos + 500
            buyer_section = text[buyer_pos:end_pos]
            self._extract_party_info(buyer_section, info, is_buyer=True)

        if seller_pos != -1 and not info.seller_name:
            seller_section = text[seller_pos:seller_pos + 500]
            self._extract_party_info(seller_section, info, is_buyer=False)

        # 税号补充提取
        tax_ids = re.findall(
            r"(?:统一社会信用代码|纳税人识别号)[/：:\s]*(?:纳税人识别号[：:\s]*)?([A-Za-z0-9]{15,20})",
            text,
        )
        if tax_ids:
            if not info.buyer_tax_id and len(tax_ids) >= 1:
                info.buyer_tax_id = tax_ids[0]
            if not info.seller_tax_id and len(tax_ids) >= 2:
                info.seller_tax_id = tax_ids[1]

    def _extract_party_info(self, section: str, info: InvoiceInfo, is_buyer: bool):
        """从区域文本中提取当事方名称和税号。"""
        name_match = self.NAME_PATTERN.search(section)
        if name_match:
            name = name_match.group(1).strip()
            name = re.split(r"[纳统地开]", name)[0].strip()
            if is_buyer:
                info.buyer_name = name
            else:
                info.seller_name = name

        tax_match = self.TAX_ID_PATTERN.search(section)
        if not tax_match:
            tax_match = self.CREDIT_CODE_PATTERN.search(section)
        if tax_match:
            if is_buyer:
                info.buyer_tax_id = tax_match.group(1)
            else:
                info.seller_tax_id = tax_match.group(1)

    def _parse_amounts(self, text: str, info: InvoiceInfo):
        """提取金额、税额、价税合计。"""
        # 从 "合 计 ¥金额 ¥税额" 行同时提取金额和税额
        match = self.SUBTOTAL_LINE_PATTERN.search(text)
        if match:
            info.amount = match.group(1).replace(",", "")
            info.tax_amount = match.group(2).replace(",", "")

        # 价税合计
        for pattern in self.TOTAL_PATTERNS:
            match = pattern.search(text)
            if match:
                info.total_amount = match.group(1).replace(",", "")
                break

    def _parse_items(self, text: str, tables: list, info: InvoiceInfo):
        """提取商品/服务名称。

        优先从表格中提取，回退到正文关键词匹配。
        """
        items = set()

        # 从表格提取
        for table in tables:
            if not table:
                continue
            for row in table:
                if not row:
                    continue
                for cell in row:
                    if not cell:
                        continue
                    cell_str = str(cell).strip()
                    # 跳过表头和常见非商品内容
                    if cell_str in ("", "货物或应税劳务、服务名称", "项目名称",
                                     "规格型号", "单位", "数量", "单价",
                                     "金额", "税率", "税额", "合计"):
                        continue
                    # 商品名称通常以 * 开头（税收分类编码简称）
                    if cell_str.startswith("*"):
                        items.add(cell_str)

        # 正文中查找 *xxx*yyy 格式的商品名
        item_pattern = re.compile(r"\*[^*\s]+\*[^\s*]+")
        for match in item_pattern.finditer(text):
            items.add(match.group())

        info.items = sorted(items)
