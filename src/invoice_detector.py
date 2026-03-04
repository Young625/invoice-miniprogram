"""发票检测模块：两级检测判断邮件/PDF 是否包含发票。

第一级：邮件主题和正文的关键词匹配（快速筛选）
第二级：PDF 内容中的发票标志检测（精确验证）

支持两种发票来源：
1. 邮件附件中的 PDF
2. 邮件正文中的发票链接（自动下载 PDF）
"""

import logging
from typing import List

import pdfplumber

# 支持相对导入和绝对导入
try:
    from .pdf_downloader import extract_pdfs_from_urls
except ImportError:
    from pdf_downloader import extract_pdfs_from_urls

logger = logging.getLogger(__name__)

# 第一级：邮件关键词
EMAIL_KEYWORDS = [
    "发票",
    "增值税",
    "电子发票",
    "数电发票",
    "全电发票",
    "专用发票",
    "普通发票",
    "税务",
    "开票",
    "invoice",
]

# 第二级：PDF 内容中的发票标志
PDF_INVOICE_MARKERS = [
    "发票号码",
    "发票代码",
    "价税合计",
    "开票日期",
    "购买方",
    "销售方",
    "纳税人识别号",
    "增值税电子普通发票",
    "增值税电子专用发票",
    "增值税普通发票",
    "增值税专用发票",
    "电子发票",
    "税额",
    "金额",
    "校验码",
    "机器编号",
]

# 至少匹配的标志数量才确认为发票
PDF_MIN_MARKER_COUNT = 3


def check_email_keywords(subject: str, body: str) -> bool:
    """第一级检测：邮件主题或正文中是否包含发票相关关键词。

    Args:
        subject: 邮件主题
        body: 邮件正文

    Returns:
        是否可能包含发票
    """
    text = f"{subject} {body}".lower()
    for keyword in EMAIL_KEYWORDS:
        if keyword.lower() in text:
            logger.debug("邮件关键词命中: '%s'", keyword)
            return True
    return False


def check_pdf_is_invoice(pdf_data: bytes) -> bool:
    """第二级检测：PDF 内容中是否包含足够的发票标志。

    Args:
        pdf_data: PDF 文件的二进制内容

    Returns:
        是否为发票 PDF
    """
    try:
        import io

        with pdfplumber.open(io.BytesIO(pdf_data)) as pdf:
            full_text = ""
            # 只检查前3页（发票通常是单页）
            for page in pdf.pages[:3]:
                page_text = page.extract_text() or ""
                full_text += page_text + "\n"

            if not full_text.strip():
                logger.debug("PDF 无法提取文本，可能是扫描件")
                return False

            matched_markers = []
            for marker in PDF_INVOICE_MARKERS:
                if marker in full_text:
                    matched_markers.append(marker)

            is_invoice = len(matched_markers) >= PDF_MIN_MARKER_COUNT
            if is_invoice:
                logger.info("PDF 发票标志命中 %d 个: %s", len(matched_markers), matched_markers)
            else:
                logger.debug(
                    "PDF 发票标志仅命中 %d 个（需要 %d 个）: %s",
                    len(matched_markers),
                    PDF_MIN_MARKER_COUNT,
                    matched_markers,
                )
            return is_invoice

    except Exception as e:
        logger.error("检测 PDF 内容时出错: %s", e)
        return False


def detect_invoices(
    subject: str, body: str, pdf_attachments: List[tuple]
) -> List[tuple]:
    """两级检测：返回确认为发票的 PDF 列表。

    支持两种来源：
    1. 邮件附件中的 PDF（pdf_attachments）
    2. 邮件正文中的发票链接（自动下载）

    Args:
        subject: 邮件主题
        body: 邮件正文
        pdf_attachments: [(文件名, 二进制内容), ...] 来自附件

    Returns:
        确认为发票的 [(文件名, 二进制内容), ...]
    """
    # 第一级：邮件关键词检查
    email_has_keywords = check_email_keywords(subject, body)

    # 收集所有 PDF 来源
    all_pdfs = list(pdf_attachments)  # 复制附件列表

    # 从邮件正文中提取链接并下载 PDF
    if email_has_keywords:
        logger.info("邮件包含发票关键词，检查正文中是否有下载链接...")
        downloaded_pdfs = extract_pdfs_from_urls(body)
        if downloaded_pdfs:
            logger.info("从链接下载了 %d 个 PDF", len(downloaded_pdfs))
            all_pdfs.extend(downloaded_pdfs)

    if not all_pdfs:
        return []

    invoice_pdfs = []
    for filename, data in all_pdfs:
        # 第二级：PDF 内容检查
        if check_pdf_is_invoice(data):
            invoice_pdfs.append((filename, data))
            logger.info("确认发票 PDF: %s", filename)
        elif email_has_keywords:
            # 如果邮件包含发票关键词但 PDF 检测没通过，记录日志便于排查
            logger.info(
                "邮件含发票关键词但 PDF 未通过检测: %s（可能是扫描件或非标准格式）",
                filename,
            )

    return invoice_pdfs
