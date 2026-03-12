"""发票 PDF 解析模块：提取发票的结构化信息。

架构：策略模式 + 工厂字典
- InvoiceParser：对外接口，负责 PDF 文本提取、类型识别、策略分发
- BaseInvoiceStrategy：公共解析逻辑基类
- 各类型策略子类：只覆盖与自身格式不同的方法

支持的发票类型：
1. 电子发票（普通发票）       - 数电发票，无发票代码，20位号码
2. 电子发票（铁路电子客票）   - 无价税合计，用票价，税率固定9%
3. 电子发票（增值税专用发票） - 数电发票，有进项税抵扣信息
4. 通用（电子）发票           - 通用格式，可能有省份前缀
5. 增值税电子普通发票         - 传统格式，有发票代码+8位号码，有密码区
6. 其他类型                   - 兜底
"""

import io
import logging
import re
from collections import Counter
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
    tax_rate: str = ""           # 税率（如：6%、9%、13%、免税）
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


# ---------------------------------------------------------------------------
# 基础解析策略（公共逻辑）
# ---------------------------------------------------------------------------

class BaseInvoiceStrategy:
    """所有发票类型的公共解析逻辑基类。

    子类只需覆盖与自身格式不同的方法，其余继承此基类。
    """

    # 发票代码模式：10-12位数字
    CODE_PATTERN = re.compile(r"发票代码[：:\s]*(\d{10,12})")

    # 发票号码模式：8位（传统）或20位（数电）
    NUMBER_PATTERNS = [
        re.compile(r"发票号码[：:\s]*(\d{20})"),   # 数电发票优先匹配
        re.compile(r"发票号码[：:\s]*(\d{8})"),     # 传统发票
        re.compile(r"No[.．：:\s]*(\d{20})"),       # 英文标识
        re.compile(r"No[.．：:\s]*(\d{8})"),
    ]

    # 开票日期模式
    DATE_PATTERNS = [
        re.compile(r"开票日期[：:\s]*(\d{4})\s*年\s*(\d{1,2})\s*.?\s*(\d{1,2})\s*.?"),
        re.compile(r"开票日期[：:\s]*(\d{4})[-./ ](\d{1,2})[-./ ](\d{1,2})"),
        # 数字间有空格的格式，如 "2 0 2 4 年 0 8 月 0 8 日"
        re.compile(r"开票日期[：:\s]*(\d\s\d\s\d\s\d)\s*年\s*(\d\s?\d)\s*月\s*(\d\s?\d)\s*日"),
        # 国家税务总局章戳格式：章 2024 09 06（开票日期行为空时日期在章戳行）
        re.compile(r"章\s+(\d{4})\s+(\d{1,2})\s+(\d{1,2})\s*$", re.MULTILINE),
    ]

    # 纳税人识别号模式：15-20位数字字母
    TAX_ID_PATTERN = re.compile(r"纳税人识别号[：:\s]*([A-Za-z0-9](?:\s?[A-Za-z0-9]){14,19})")

    # 统一社会信用代码也可作为税号
    CREDIT_CODE_PATTERN = re.compile(
        r"统一社会信用代码[/：:\s]*\n*\s*纳税人识别号[：:\s]*([A-Za-z0-9](?:\s?[A-Za-z0-9]){14,19})"
    )

    TAX_RATE_PATTERNS = [
        re.compile(r"税率[/\\]*征收率[：:\s]*([0-9.]+)%"),
        re.compile(r"税率[：:\s]*([0-9.]+)%"),
        re.compile(r"征收率[：:\s]*([0-9.]+)%"),
        re.compile(r"税\s*率[：:\s]*([0-9.]+)%"),
        re.compile(r"(?:税率|征收率).*?([0-9.]+)%"),
    ]

    # 数电发票商品明细行税率：*商品名*描述 ... 金额 税率% 税额
    ITEM_LINE_RATE_PATTERN = re.compile(
        r"\*[^*\n]+\*[^\n]*\s(\d+(?:\.\d+)?)%",
        re.MULTILINE,
    )

    # "合 计" 行同时提取金额和税额
    # 格式1（传统）：合 计 ¥192.08 ¥1.92  — 金额在"合计"之后
    # 格式2（数电）：¥8.55 ¥0.25\n合 计  — 金额在"合计"之前一行
    SUBTOTAL_LINE_PATTERN = re.compile(
        r"合\s*计\s*[¥￥]?\s*([\d,]+\.\d{2})\s*[¥￥]?\s*([\d,]+\.\d{2})"
    )
    # 数电发票：金额行在"合计"文字上方，格式为 ¥8.55 ¥0.25\n合 计
    SUBTOTAL_BEFORE_PATTERN = re.compile(
        r"[¥￥]\s*([\d,]+\.\d{2})\s+[¥￥]\s*([\d,]+\.\d{2})\s*\n\s*合\s*计"
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

    def parse_fields(self, text: str, tables: list, info: InvoiceInfo):
        """按顺序调用各字段解析方法（模板方法）。"""
        self.parse_code_and_number(text, info)
        self.parse_date(text, info)
        self.parse_buyer_seller(text, tables, info)
        self.parse_amounts(text, tables, info)
        self.parse_items(text, tables, info)

    def parse_code_and_number(self, text: str, info: InvoiceInfo):
        """提取发票代码和号码。"""
        match = self.CODE_PATTERN.search(text)
        if match:
            info.invoice_code = match.group(1)

        for pattern in self.NUMBER_PATTERNS:
            match = pattern.search(text)
            if match:
                info.invoice_number = match.group(1)
                break

        # 备用策略：PDF乱序时号码出现在其他行
        if not info.invoice_number:
            m = re.search(r'(?:^|\s|制\s*)(\d{20})(?:\s|$)', text, re.MULTILINE)
            if m:
                info.invoice_number = m.group(1)
        if not info.invoice_number and info.invoice_code:
            m = re.search(r'(?:^|\s)(\d{8})(?:\s|$)', text, re.MULTILINE)
            if m:
                info.invoice_number = m.group(1)

    def parse_date(self, text: str, info: InvoiceInfo):
        """提取开票日期。"""
        for pattern in self.DATE_PATTERNS:
            match = pattern.search(text)
            if match:
                year = match.group(1).replace(" ", "")
                month = match.group(2).replace(" ", "")
                day = match.group(3).replace(" ", "")
                info.invoice_date = f"{year}-{int(month):02d}-{int(day):02d}"
                return

        m = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', text)
        if m:
            year, month, day = m.group(1), m.group(2), m.group(3)
            if 2015 <= int(year) <= 2030:
                info.invoice_date = f"{year}-{int(month):02d}-{int(day):02d}"
                return
        m = re.search(r'(\d{4})\s+年\s+(\d{1,2})\s+月\s+(\d{1,2})\s*日', text)
        if m:
            year, month, day = m.group(1), m.group(2), m.group(3)
            if 2015 <= int(year) <= 2030:
                info.invoice_date = f"{year}-{int(month):02d}-{int(day):02d}"

    def parse_buyer_seller(self, text: str, tables: list, info: InvoiceInfo):
        """提取购买方和销售方信息。优先从表格提取，回退到纯文本。"""
        if not self._parse_buyer_seller_from_tables(tables, info):
            self._parse_buyer_seller_from_text(text, info)

        _tax_suffix = re.compile(r'\s*(?:统.社会信用代码|纳税.识别号).*', re.DOTALL)
        if info.buyer_name:
            info.buyer_name = _tax_suffix.sub("", info.buyer_name).strip()
        if info.seller_name:
            info.seller_name = _tax_suffix.sub("", info.seller_name).strip()

    def _parse_buyer_seller_from_tables(self, tables: list, info: InvoiceInfo) -> bool:
        """从表格中提取购买方/销售方信息。"""
        found = False
        for table in tables:
            if not table:
                continue
            for row in table:
                if not row:
                    continue

                # 先找出买方列索引和卖方列索引（标签单元格）
                buyer_col = seller_col = None
                for i, cell in enumerate(row):
                    cell_s = str(cell or "")
                    if any(k in cell_s for k in ["购买方", "购\n买", "购 买"]):
                        buyer_col = i
                    if any(k in cell_s for k in ["销售方", "销\n售", "销 售"]):
                        seller_col = i

                # 逐 cell 提取，根据列位置判断归属
                for ci, cell in enumerate(row):
                    if not cell:
                        continue
                    cell_str = str(cell)

                    # 判断当前 cell 属于买方还是卖方区域
                    if buyer_col is not None and seller_col is not None:
                        # 买方列在卖方列左边：ci <= seller_col 的左半属于买方
                        is_buyer_cell = (buyer_col <= ci < seller_col)
                        is_seller_cell = (ci >= seller_col)
                    elif buyer_col is not None:
                        is_buyer_cell = (ci > buyer_col)
                        is_seller_cell = False
                    elif seller_col is not None:
                        is_buyer_cell = (ci < seller_col)
                        is_seller_cell = (ci >= seller_col)
                    else:
                        # 无明确标签列，回退到关键词判断
                        is_buyer_cell = any(k in str(r or "") for r in row for k in ["购", "买方"])
                        is_seller_cell = any(k in str(r or "") for r in row for k in ["销", "售方"])

                    # 格式1：名称：公司名（标签在前）
                    name_match = re.search(r"名\s*称[：:]\s*(.+?)(?:\n|$)", cell_str)
                    # 格式2：公司名\n名称：（标签在后，数电发票常见格式）— 优先级更高
                    name_match_before = re.match(r"(.+?)\n名\s*称[：:]", cell_str)
                    if name_match_before:
                        name_match = name_match_before  # group(1) 即公司名
                    tax_match = re.search(
                        r"(?:统.社会信用代码|纳税.识别号)[/：:\s]*(?:纳税.识别号[：:\s]*)?([A-Za-z0-9](?:\s?[A-Za-z0-9]){14,19})",
                        cell_str,
                    )

                    if name_match:
                        name = name_match.group(1).strip()
                        if name and is_buyer_cell and not info.buyer_name:
                            info.buyer_name = name
                            found = True
                        elif name and is_seller_cell and not info.seller_name:
                            info.seller_name = name
                            found = True

                    if tax_match:
                        tax_id = tax_match.group(1).replace(" ", "")
                        if is_buyer_cell and not info.buyer_tax_id:
                            info.buyer_tax_id = tax_id
                            found = True
                        elif is_seller_cell and not info.seller_tax_id:
                            info.seller_tax_id = tax_id
                            found = True

        return found

    def _parse_buyer_seller_from_text(self, text: str, info: InvoiceInfo):
        """从纯文本中提取购买方/销售方信息（传统发票格式）。"""
        line_pattern = re.compile(
            r"购\s*名称[：:]\s*(.+?)\s+销\s*名称[：:]\s*(.+?)$", re.MULTILINE
        )
        match = line_pattern.search(text)
        if match:
            if not info.buyer_name:
                info.buyer_name = match.group(1).strip()
            if not info.seller_name:
                info.seller_name = match.group(2).strip()

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
            self._extract_party_info(text[buyer_pos:end_pos], info, is_buyer=True)

        if seller_pos != -1 and not info.seller_name:
            self._extract_party_info(text[seller_pos:seller_pos + 500], info, is_buyer=False)

        # 税号补充提取
        tax_ids = re.findall(
            r"(?:统.社会信用代码|纳税.识别号)[/：:\s]*(?:纳税.识别号[：:\s]*)?([A-Za-z0-9](?:\s?[A-Za-z0-9]){14,19})",
            text,
        )
        if tax_ids:
            if not info.buyer_tax_id and len(tax_ids) >= 1:
                info.buyer_tax_id = tax_ids[0].replace(" ", "")
            if not info.seller_tax_id and len(tax_ids) >= 2:
                info.seller_tax_id = tax_ids[1].replace(" ", "")

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
                info.buyer_tax_id = tax_match.group(1).replace(" ", "")
            else:
                info.seller_tax_id = tax_match.group(1).replace(" ", "")

    def parse_amounts(self, text: str, tables: list, info: InvoiceInfo):
        """提取金额、税额、价税合计、税率。"""
        # 优先从表格"合计"行直接读取（单元格值最准确，无精度问题）
        self._parse_amounts_from_tables(tables, info)

        # 文本匹配：格式1 — 合 计 ¥xx ¥xx（传统格式，金额在"合计"之后）
        if not info.amount or not info.tax_amount:
            match = self.SUBTOTAL_LINE_PATTERN.search(text)
            if match:
                info.amount = float(match.group(1).replace(",", ""))
                info.tax_amount = float(match.group(2).replace(",", ""))

        # 文本匹配：格式2 — ¥xx ¥xx\n合 计（数电发票，金额在"合计"之前）
        if not info.amount or not info.tax_amount:
            match = self.SUBTOTAL_BEFORE_PATTERN.search(text)
            if match:
                info.amount = float(match.group(1).replace(",", ""))
                info.tax_amount = float(match.group(2).replace(",", ""))

        for pattern in self.TOTAL_PATTERNS:
            match = pattern.search(text)
            if match:
                info.total_amount = float(match.group(1).replace(",", ""))
                break

        self._parse_tax_rate(text, tables, info)

        if info.total_amount and (not info.amount or not info.tax_amount):
            self._calculate_missing_amounts(info)

    def _parse_amounts_from_tables(self, tables: list, info: InvoiceInfo):
        """从表格中定位"合计"行，直接读取金额和税额单元格。"""
        # 表格列顺序通常为：名称 | 规格 | 单位 | 数量 | 单价 | 金额 | 税率 | 税额
        # 找到含"金额"和"税额"的表头行，记录列索引，再从"合计"行取值
        AMOUNT_HEADERS = {"金额", "金 额", "全额", "全 额"}
        TAX_HEADERS = {"税额", "税 额"}
        MONEY_RE = re.compile(r"[¥￥]?\s*([\d,]+\.\d{2})")
        # 数电发票大单元格：整个明细区域在一个 cell 里，用此 pattern 直接提取合计行
        CELL_SUBTOTAL_RE = re.compile(
            r"[¥￥]\s*([\d,]+\.\d{2})\s+[¥￥]\s*([\d,]+\.\d{2})\s*\n\s*合\s*计"
        )

        for table in (tables or []):
            if not table:
                continue
            amount_col = tax_col = None
            for row in table:
                if not row:
                    continue
                cells = [str(c).strip() if c else "" for c in row]

                # 数电发票：整个明细区域在 cells[0] 一个大单元格里
                if len(cells) >= 1 and cells[0]:
                    m = CELL_SUBTOTAL_RE.search(cells[0])
                    if m and not info.amount and not info.tax_amount:
                        info.amount = float(m.group(1).replace(",", ""))
                        info.tax_amount = float(m.group(2).replace(",", ""))
                        return

                # 识别表头行，确定列索引
                for i, c in enumerate(cells):
                    if c in AMOUNT_HEADERS:
                        amount_col = i
                    if c in TAX_HEADERS:
                        tax_col = i

                # 识别合计行（某个单元格含"合计"关键词，用 regex 兼容多空格）
                is_subtotal = any(
                    re.search(r"合\s*计", c) for c in cells if c
                )
                if not is_subtotal:
                    continue

                # 从已知列索引取值
                def extract_money(cell_text: str) -> float | None:
                    # 单元格可能含多行，取最后一个金额（合计行的值）
                    matches = MONEY_RE.findall(cell_text)
                    if matches:
                        try:
                            return float(matches[-1].replace(",", ""))
                        except ValueError:
                            pass
                    return None

                if amount_col is not None and amount_col < len(cells):
                    v = extract_money(cells[amount_col])
                    if v is not None and not info.amount:
                        info.amount = v
                if tax_col is not None and tax_col < len(cells):
                    v = extract_money(cells[tax_col])
                    if v is not None and not info.tax_amount:
                        info.tax_amount = v

                if info.amount and info.tax_amount:
                    return
                    v = extract_money(cells[amount_col])
                    if v is not None and not info.amount:
                        info.amount = v
                if tax_col is not None and tax_col < len(cells):
                    v = extract_money(cells[tax_col])
                    if v is not None and not info.tax_amount:
                        info.tax_amount = v

                if info.amount and info.tax_amount:
                    return

    def _calculate_missing_amounts(self, info: InvoiceInfo):
        """根据价税合计和税率反推缺失的金额或税额。"""
        if not info.total_amount:
            return
        try:
            total = float(info.total_amount)
            if info.tax_rate is not None:
                rate = float(info.tax_rate) / 100.0
                if rate == 0:
                    if not info.amount:
                        info.amount = total
                    if not info.tax_amount:
                        info.tax_amount = 0.0
                else:
                    amount = round(total / (1 + rate), 2)
                    tax = round(total - amount, 2)
                    if not info.amount:
                        info.amount = amount
                    if not info.tax_amount:
                        info.tax_amount = tax
            elif info.amount and not info.tax_amount:
                info.tax_amount = round(total - float(info.amount), 2)
            elif info.tax_amount and not info.amount:
                info.amount = round(total - float(info.tax_amount), 2)
        except (ValueError, ZeroDivisionError):
            pass

    def _parse_tax_rate(self, text: str, tables: list, info: InvoiceInfo):
        """从文本和表格中提取税率。"""
        if re.search(r'不征税|免税', text):
            info.tax_rate = "0"
            return

        for pattern in self.TAX_RATE_PATTERNS:
            match = pattern.search(text)
            if match:
                info.tax_rate = match.group(1)
                return

        matches = self.ITEM_LINE_RATE_PATTERN.findall(text)
        if matches:
            info.tax_rate = Counter(matches).most_common(1)[0][0]
            return

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
                    if re.match(r'^\*+$', cell_str):
                        info.tax_rate = "0"
                        return
                    rate_match = re.match(r'^([0-9.]+)%$', cell_str)
                    if rate_match:
                        row_text = " ".join(str(c) for c in row if c)
                        if "税率" in row_text or "征收率" in row_text:
                            info.tax_rate = rate_match.group(1)
                            return
                    if len(cell_str) > 10:
                        if re.search(r'不征税|免税', cell_str):
                            info.tax_rate = "0"
                            return
                        for p in self.TAX_RATE_PATTERNS:
                            m = p.search(cell_str)
                            if m:
                                info.tax_rate = m.group(1)
                                return
                        cell_matches = self.ITEM_LINE_RATE_PATTERN.findall(cell_str)
                        if cell_matches:
                            info.tax_rate = Counter(cell_matches).most_common(1)[0][0]
                            return

    # 表格中常见的规格型号/单位词，不应被拼入商品名称
    _UNIT_WORDS = re.compile(
        r"^(无|次|个|件|套|台|只|条|张|份|月|年|天|日|批|箱|包|袋|瓶|罐|升|千克|吨|米|"
        r"平方米|立方米|公里|千米|小时|分钟|秒|人次|人天|人月|辆|艘|架|栋|间|项|式|组|"
        r"块|片|粒|支|根|卷|本|册|幅|幢|座|处|段|节|行|列|页|字|点|度|瓦|千瓦|兆瓦)$"
    )

    @staticmethod
    def _clean_item_name(name: str) -> str:
        """截掉商品名称末尾混入的规格型号/单位词（如"无 次"）。"""
        # 去掉末尾形如 " 无 次" 或 " 次" 的单位/规格词
        return re.sub(r"(\s+\S+){0,3}$",
                      lambda m: "" if all(
                          BaseInvoiceStrategy._UNIT_WORDS.match(w)
                          for w in m.group().split() if w
                      ) else m.group(),
                      name).strip()

    def parse_items(self, text: str, tables: list, info: InvoiceInfo):
        """提取商品/服务名称。优先从表格提取，回退到正文关键词匹配。"""
        items = set()

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
                    if cell_str in ("", "货物或应税劳务、服务名称", "项目名称",
                                    "规格型号", "单位", "数量", "单价",
                                    "金额", "税率", "税额", "合计"):
                        continue
                    if cell_str.startswith("*"):
                        first_cat = re.match(r'\*([^*]+)\*', cell_str)
                        if first_cat and re.search(r'[\u4e00-\u9fff]', first_cat.group(1)):
                            items.add(self._clean_item_name(cell_str))
                    elif len(cell_str) > 10 and "\n" in cell_str:
                        for item in self._extract_items_from_cell(cell_str):
                            items.add(item)
                        # 通用电子发票：货物或应税劳务、服务名称列中包含商品名
                        if "货物或应税劳务" in cell_str or "服务名称" in cell_str:
                            for line in cell_str.split("\n"):
                                line = line.strip()
                                if (line and line not in ("", "货物或应税劳务、服务名称", "项目名称",
                                                          "规格型号", "单位", "数量", "单价",
                                                          "金额", "税率", "税额", "合计", "合 计")
                                    and not re.match(r'^[\d.\s¥￥*]+$', line)):
                                    items.add(line)

        item_pattern = re.compile(r"\*[^*\n]+\*[^\n]+", re.MULTILINE)
        for match in item_pattern.finditer(text):
            raw = match.group()
            name = re.split(r"\s+\d", raw)[0].strip()
            name = self._clean_item_name(name)
            name = self._join_wrapped_name(text, match.start(), name)
            first_cat = re.match(r'\*([^*]+)\*', name) if name else None
            if first_cat and re.search(r'[\u4e00-\u9fff]', first_cat.group(1)):
                items.add(name)

        # 去重：如果一个条目是另一个条目的前缀，保留较短的
        deduped = set()
        for item in sorted(items, key=len):
            if not any(item.startswith(shorter) for shorter in deduped):
                deduped.add(item)
        info.items = sorted(deduped)

    def _extract_items_from_cell(self, cell_str: str) -> list:
        """从合并单元格文本中提取商品名称，处理折行情况。"""
        results = []
        lines = cell_str.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("*"):
                name_part = re.split(r"\s+\d", line)[0].strip()
                name_part = self._clean_item_name(name_part)
                # 判断下一行是否是名称的折行续接（而非单位/规格列）
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if (next_line
                            and not next_line.startswith("*")
                            and not re.match(r"^[\d¥￥合]", next_line)
                            and not re.search(r"\d+\.\d{2}", next_line)
                            and not self._UNIT_WORDS.match(next_line)
                            and re.search(r"[\u4e00-\u9fff]", next_line)):
                        name_part = name_part + next_line
                        i += 1
                results.append(name_part)
            i += 1
        return [r for r in results
                if (m := re.match(r'\*([^*]+)\*', r)) and re.search(r'[\u4e00-\u9fff]', m.group(1))]

    def _join_wrapped_name(self, text: str, match_start: int, name: str) -> str:
        """检测商品名是否被折行截断，若是则拼接下一行的续接内容。"""
        line_end = text.find("\n", match_start)
        if line_end == -1:
            return name
        next_line_start = line_end + 1
        next_line_end = text.find("\n", next_line_start)
        next_line = (text[next_line_start:next_line_end].strip()
                     if next_line_end != -1 else text[next_line_start:].strip())
        if (next_line
                and not next_line.startswith("*")
                and not re.match(r"^[\d¥￥合价]", next_line)
                and not re.search(r"\d+\.\d{2}", next_line)
                and not self._UNIT_WORDS.match(next_line)
                and re.search(r"[\u4e00-\u9fff]", next_line)
                and len(next_line) <= 15):
            return name + next_line
        return name


# ---------------------------------------------------------------------------
# 各发票类型专用策略（只覆盖与基类不同的方法）
# ---------------------------------------------------------------------------

class RailwayTicketStrategy(BaseInvoiceStrategy):
    """电子发票（铁路电子客票）专用解析策略。

    差异点：
    - 无"价税合计"字段，用"票价"字段作为发票金额
    - 税率固定 9%，PDF 上不显示
    - 购买方格式为单行 "购买方名称:xxx 统一社会信用代码:yyy"
    - items 留空（铁路客票无商品明细）
    """

    def parse_amounts(self, text: str, tables: list, info: InvoiceInfo):
        """铁路客票金额提取：用票价替代价税合计，税率固定9%。"""
        # 策略1：票价: ¥409.00 或 票价：409.00
        m = re.search(r"票\s*价[：:\s]*[¥￥]\s*([\d,]+\.\d{2})", text)
        if m:
            info.total_amount = float(m.group(1).replace(",", ""))
        # 策略2：乱序情况 — 文本含"票价"，且有独立的 ¥金额行
        elif re.search(r"票\s*价", text):
            m = re.search(r"[¥￥]\s*([\d,]+\.\d{2})", text)
            if m:
                info.total_amount = float(m.group(1).replace(",", ""))

        # 税率固定 9%，但铁路客票不显示分拆的金额/税额，不做反推计算
        info.tax_rate = "9"

    def _parse_buyer_seller_from_text(self, text: str, info: InvoiceInfo):
        """铁路客票购买方格式：单行 "购买方名称:xxx 统一社会信用代码:yyy"。"""
        if not info.buyer_name:
            m = re.search(
                r"购买方名称[：:]\s*(.+?)(?:\s+统一社会信用代码|$)", text, re.MULTILINE
            )
            if m:
                info.buyer_name = m.group(1).strip()

        # 税号补充（复用基类逻辑）
        tax_ids = re.findall(
            r"(?:统一社会信用代码|纳税人识别号)[/：:\s]*(?:纳税人识别号[：:\s]*)?([A-Za-z0-9]{15,20})",
            text,
        )
        if tax_ids:
            if not info.buyer_tax_id and len(tax_ids) >= 1:
                info.buyer_tax_id = tax_ids[0].replace(" ", "")
            if not info.seller_tax_id and len(tax_ids) >= 2:
                info.seller_tax_id = tax_ids[1].replace(" ", "")


class DigitalInvoiceStrategy(BaseInvoiceStrategy):
    """电子发票（普通发票）专用解析策略。

    数电发票新格式：无发票代码，20位号码，表格结构规整。
    购销方信息在表格单元格中，基类的表格优先逻辑已能正确处理。
    """
    pass


class DigitalVatSpecialStrategy(BaseInvoiceStrategy):
    """电子发票（增值税专用发票）专用解析策略。

    数电发票新格式，有进项税抵扣信息。
    当前与数电普通发票解析逻辑一致，未来可在此扩展专票特有字段。
    """
    pass


class GeneralElectronicInvoiceStrategy(BaseInvoiceStrategy):
    """通用（电子）发票专用解析策略。

    格式类似数电发票，可能有省份前缀（如"全国通用（电子）发票"）。
    当前与基类逻辑一致。
    """
    pass


class VatElectronicInvoiceStrategy(BaseInvoiceStrategy):
    """增值税电子普通发票（传统格式）专用解析策略。

    差异点：
    - 有密码区（干扰商品名提取，基类已通过中文过滤处理）
    - 传统表格格式，有发票代码（10-12位）+ 发票号码（8位）
    - PDF 多列布局导致文字乱序：标签行与值行分离，需特殊处理
    - 价税合计仅在表格单元格中，基类全文搜索无法提取
    - 税率在表格单元格以 "税率\n13%" 多行格式存储
    """

    def parse_code_and_number(self, text: str, info: InvoiceInfo):
        """提取发票代码和号码（处理标签与值分行的乱序格式）。"""
        # 先尝试基类（处理格式规范的 PDF）
        super().parse_code_and_number(text, info)
        if info.invoice_code and info.invoice_number:
            return

        # 发票代码：找文本中第一个独立的 10-12 位数字
        if not info.invoice_code:
            m = re.search(r'(?<!\d)(\d{10,12})(?!\d)', text)
            if m:
                info.invoice_code = m.group(1)

    def parse_items(self, text: str, tables: list, info: InvoiceInfo):
        """提取商品名称，并去除因 PDF 列拆分导致的重复项。"""
        super().parse_items(text, tables, info)
        if len(info.items) <= 1:
            return
        # 去重：若同时存在 "*X*Y" 和 "X*Y"（无前缀 *），保留带 * 前缀的版本
        seen = {}
        for item in info.items:
            key = item.lstrip('*')
            if key not in seen or item.startswith('*'):
                seen[key] = item
        info.items = list(seen.values())

        # 发票号码：优先匹配 "统一发票监 XXXXXXXX"
        if not info.invoice_number:
            m = re.search(r'统一发票监\s*(\d{8})(?:\s|$)', text)
            if not m:
                m = re.search(r'(?<!\d)(\d{8})(?!\d)', text)
            if m:
                info.invoice_number = m.group(1)

    @staticmethod
    def _merge_split_cells(row: list) -> list:
        """合并被拆分的数字单元格。

        pdfplumber 有时把 "47.12" 拆成相邻两格 ["47.1", "2"]。
        策略：若某格只含纯数字/小数点，且前一格以数字结尾，则拼接。
        """
        merged = []
        for cell in row:
            s = str(cell).strip() if cell is not None else ''
            if (merged and re.match(r'^\d+$', s)
                    and merged[-1] and re.search(r'\d$', merged[-1])):
                merged[-1] = merged[-1] + s
            else:
                merged.append(s)
        return merged

    def parse_amounts(self, text: str, tables: list, info: InvoiceInfo):
        """提取金额（直接从表格单元格读取，避免基类跨行误匹配）。"""
        MONEY_RE = re.compile(r'(\d[\d,]*\.\d{2})')
        # 价税合计：支持有/无 ¥ 两种格式
        xiaoxie_re = re.compile(r'[（(]小写[）)]\s*[¥￥]?\s*([\d,]+\.\d{2})')

        for table in (tables or []):
            for row in (table or []):
                if not row:
                    continue
                cells = self._merge_split_cells(row)

                # 识别含"合计"的明细行（同时含商品名和合计）
                has_subtotal = any(re.search(r'合\s*计', c) for c in cells if c)
                if not has_subtotal:
                    continue

                # 从含"金 额"的单元格取不含税金额
                # 多行商品时单元格含多个金额，取 ¥NNN.NN 格式的合计值；否则取最后一个数字
                for cell in cells:
                    if re.search(r'金\s*额', cell) and not re.search(r'价税合计', cell):
                        m_yen = re.search(r'[¥￥]\s*([\d,]+\.\d{2})', cell)
                        if m_yen and not info.amount:
                            info.amount = float(m_yen.group(1).replace(',', ''))
                        elif not info.amount:
                            nums = MONEY_RE.findall(cell)
                            if nums:
                                info.amount = float(nums[-1].replace(',', ''))
                        break

                # 从含"税 额"的单元格取税额
                # 多行商品时取 ¥NNN.NN 格式的合计值；*** 表示不征税则跳过
                for cell in cells:
                    if re.search(r'税\s*额', cell) and not re.search(r'税率', cell):
                        m_yen = re.search(r'[¥￥]\s*([\d,]+\.\d{2})', cell)
                        if m_yen and not info.tax_amount:
                            try:
                                info.tax_amount = float(m_yen.group(1).replace(',', ''))
                            except ValueError:
                                pass
                        break

            # 从价税合计行取 total_amount
            for row in (table or []):
                if not row:
                    continue
                merged_row = self._merge_split_cells(row)
                for cell in merged_row:
                    if not cell:
                        continue
                    m = xiaoxie_re.search(cell)
                    if m:
                        info.total_amount = float(m.group(1).replace(',', ''))
                        break

        # 税率：从表格单元格 "税率\n13%" 或 "税率\n不征税" 多行格式提取
        for table in (tables or []):
            for row in (table or []):
                for cell in (row or []):
                    if not cell:
                        continue
                    cell_str = str(cell)
                    if re.search(r'税率\s*\n\s*(不征税|免税)', cell_str):
                        info.tax_rate = "0"
                        return
                    m = re.search(r'税率\s*\n\s*(\d+(?:\.\d+)?)%', cell_str)
                    if m:
                        info.tax_rate = m.group(1)
                        return

        # 兜底：基类文本匹配（处理表格提取失败的情况）
        if not info.total_amount or not info.amount:
            super().parse_amounts(text, tables, info)


class UnknownInvoiceStrategy(BaseInvoiceStrategy):
    """其他类型兜底策略，尝试提取票据代码/号码、项目名称、金额等通用字段。"""

    def parse_code_and_number(self, text: str, info: InvoiceInfo):
        """提取票据代码和号码（兼容发票和票据格式）。"""
        # 先尝试标准发票格式
        super().parse_code_and_number(text, info)

        # 如果没提取到，尝试票据格式：票据代码：xxx 票据号码：xxx
        if not info.invoice_code:
            m = re.search(r'票据代码[：:\s]*(\d{8,})', text)
            if m:
                info.invoice_code = m.group(1)

        if not info.invoice_number:
            m = re.search(r'票据号码[：:\s]*(\d{8,})', text)
            if m:
                info.invoice_number = m.group(1)

    def parse_items(self, text: str, tables: list, info: InvoiceInfo):
        """提取项目名称（兼容发票和票据格式）。"""
        # 先尝试标准发票格式
        super().parse_items(text, tables, info)

        # 如果没提取到，尝试从表格"项目名称"列提取
        if not info.items:
            for table in tables:
                if not table or len(table) < 2:
                    continue
                # 查找"项目名称"列索引
                header = table[0]
                name_col_idx = None
                for i, cell in enumerate(header):
                    if cell and '项目名称' in str(cell):
                        name_col_idx = i
                        break

                if name_col_idx is not None:
                    for row in table[1:]:
                        if len(row) > name_col_idx and row[name_col_idx]:
                            item_name = str(row[name_col_idx]).strip()
                            if (item_name and item_name not in ('', '项目名称', '合计', '金额合计')
                                and not re.match(r'^[\d.\s¥￥]+$', item_name)):
                                info.items.append(item_name)

    def parse_amounts(self, text: str, tables: list, info: InvoiceInfo):
        """提取金额（兼容发票和票据格式）。"""
        # 先尝试标准发票格式
        super().parse_amounts(text, tables, info)

        # 如果没提取到总金额，尝试从"金额合计"行提取
        if not info.total_amount:
            # 格式1：金额合计（大写）xxx （小写）12.34
            m = re.search(r'金额合计[^¥￥]*[（(]小写[）)]\s*[¥￥]?\s*([\d,]+\.?\d*)', text)
            if m:
                info.total_amount = m.group(1).replace(',', '')
            else:
                # 格式2：金额合计 12.34
                m = re.search(r'金额合计[：:\s]*[¥￥]?\s*([\d,]+\.\d{2})', text)
                if m:
                    info.total_amount = m.group(1).replace(',', '')

    def parse_buyer_seller(self, text: str, tables: list, info: InvoiceInfo):
        """提取购买方和销售方信息（兼容发票和票据格式）。"""
        # 先尝试标准发票格式
        super().parse_buyer_seller(text, tables, info)

        # 如果没提取到购买方信息，尝试票据格式
        if not info.buyer_name:
            # 格式：交款人：xxx（排除"交款人统一社会信用代码"等带修饰词的行）
            m = re.search(r'交款人[：:]\s*([^\s\n]+(?:\s+[^\s\n]+)*?)(?:\s+开票日期|\s*$)', text, re.MULTILINE)
            if m:
                info.buyer_name = m.group(1).strip()

        if not info.buyer_tax_id:
            # 格式：交款人统一社会信用代码：xxx 或 交款人纳税人识别号：xxx
            m = re.search(r'交款人(?:统一社会信用代码|纳税人识别号)[：:\s]*([A-Za-z0-9]{15,20})', text)
            if m:
                info.buyer_tax_id = m.group(1)


# ---------------------------------------------------------------------------
# 类型 → 策略 映射表
# ---------------------------------------------------------------------------

STRATEGY_MAP: dict = {
    "电子发票（铁路电子客票）":    RailwayTicketStrategy,
    "电子发票（普通发票）":         DigitalInvoiceStrategy,
    "电子发票（增值税专用发票）":   DigitalVatSpecialStrategy,
    "通用（电子）发票":             GeneralElectronicInvoiceStrategy,
    "增值税电子普通发票":           VatElectronicInvoiceStrategy,
    "其他类型":                     UnknownInvoiceStrategy,
}


# ---------------------------------------------------------------------------
# 对外接口（向后兼容，调用方零修改）
# ---------------------------------------------------------------------------

class InvoiceParser:
    """发票 PDF 解析器（对外接口）。

    职责：
    1. 提取 PDF 文本和表格
    2. 识别发票类型
    3. 根据类型从 STRATEGY_MAP 选择对应策略
    4. 委托策略执行字段解析

    接口签名与原版完全一致，调用方（email_service.py 等）无需修改。
    """

    # 发票类型识别模式
    # 注意：部分PDF提取的文字含康熙部首异体字（如 U+2F26 ⼦），需特殊处理
    # 铁路客票用元组 (pattern1, pattern2) 表示"两个关键词都存在"
    TYPE_PATTERNS = [
        # 铁路电子客票（PDF文字可能乱序，铁路+客票同时出现即可）
        (("铁路", "客票"), "电子发票（铁路电子客票）"),
        # 电子发票新格式（兼容康熙部首异体字 ⼦ U+2F26）— 同行格式
        (r"[电電][\u5b50\u2f26]\s*发\s*票\s*[（(]\s*增值税专用发票\s*[）)]", "电子发票（增值税专用发票）"),
        (r"[电電][\u5b50\u2f26]\s*发\s*票\s*[（(]\s*普通发票\s*[）)]", "电子发票（普通发票）"),
        # 印章干扰导致"（普通发票）"被打散，但"电子发票"和"普"字都存在
        ((r"[电電][\u5b50\u2f26]\s*发\s*票", r"普通发票|统一普"), "电子发票（普通发票）"),
        # 同理：增值税专用发票跨行
        ((r"[电電][\u5b50\u2f26]\s*发\s*票", r"增值税专用发票"), "电子发票（增值税专用发票）"),
        # 通用（电子）发票（去除省份/地区前缀，如"全国通用（电子）发票"）
        (r"通用[（(]电子[）)]发票", "通用（电子）发票"),
        # 统一普通发票（部分PDF乱序提取后呈现为"统一普通发票"，等同于通用（电子）发票）
        (r"统一普通发票", "通用（电子）发票"),
        # 增值税电子普通发票（含省份前缀也能匹配，如"浙江增值税电子普通发票"）
        (r"增值税电子普通发票", "增值税电子普通发票"),
    ]

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
                    full_text += (page.extract_text() or "") + "\n"
                    tables.extend(page.extract_tables() or [])

            if not full_text.strip():
                logger.warning("PDF 无法提取文本")
                return info

            # 早期拦截：运单明细、行程单等非发票附件，直接跳过
            if self._is_non_invoice(full_text):
                logger.info("跳过非发票附件: %s", full_text[:50].replace("\n", " "))
                return info

            # 步骤1：识别发票类型
            self._parse_type(full_text, info)

            # 步骤2：根据类型选择策略并委托解析
            strategy_cls = STRATEGY_MAP.get(info.invoice_type, UnknownInvoiceStrategy)
            strategy_cls().parse_fields(full_text, tables, info)

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

    # 非发票附件的特征模式（运单明细、行程单等）
    NON_INVOICE_PATTERNS = [
        re.compile(r"运单明细"),          # 顺丰运单明细
        re.compile(r"行程单"),            # 出行行程单
        re.compile(r"运单号码.*寄件"),    # 含运单号+寄件字段
    ]

    def _is_non_invoice(self, text: str) -> bool:
        """判断是否为非发票附件（运单明细、行程单等），返回 True 则跳过入库。"""
        first_200 = text[:200]
        return any(p.search(first_200) for p in self.NON_INVOICE_PATTERNS)

    def _parse_type(self, text: str, info: InvoiceInfo):
        """识别发票类型。"""
        for pattern, type_name in self.TYPE_PATTERNS:
            if isinstance(pattern, tuple):
                if all(re.search(kw, text) for kw in pattern):
                    info.invoice_type = type_name
                    return
            elif re.search(pattern, text):
                info.invoice_type = type_name
                return
        info.invoice_type = "其他类型"
