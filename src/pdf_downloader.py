"""PDF 下载模块：从邮件正文中提取链接并下载 PDF。

支持：
- URL 提取（http/https）
- 自动跟随重定向
- PDF 有效性验证
- 超时和错误处理
"""

import logging
import re
from typing import List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

# URL 提取正则（匹配 http/https 开头的完整 URL）
URL_PATTERN = re.compile(
    r'https?://[^\s<>"{}|\\^`\[\]]+',
    re.IGNORECASE
)

# PDF 文件头标识（%PDF-）
PDF_MAGIC_BYTES = b'%PDF-'

# 下载配置
DEFAULT_TIMEOUT = 30  # 秒
MAX_PDF_SIZE = 50 * 1024 * 1024  # 50MB
USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'


def extract_urls_from_text(text: str) -> List[str]:
    """从文本中提取所有 HTTP/HTTPS URL。

    Args:
        text: 邮件正文或任意文本

    Returns:
        提取到的 URL 列表（去重）
    """
    if not text:
        return []

    urls = URL_PATTERN.findall(text)
    # 去重并保持顺序
    seen = set()
    unique_urls = []
    for url in urls:
        # 清理末尾可能的标点符号
        url = url.rstrip('.,;:!?)')
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)

    logger.debug("从文本中提取到 %d 个 URL", len(unique_urls))
    return unique_urls


def is_valid_pdf(data: bytes) -> bool:
    """验证二进制数据是否为有效 PDF。

    Args:
        data: 二进制数据

    Returns:
        是否为 PDF 格式
    """
    if not data or len(data) < 5:
        return False
    return data[:5] == PDF_MAGIC_BYTES


def download_pdf_from_url(
    url: str,
    timeout: int = DEFAULT_TIMEOUT,
    max_size: int = MAX_PDF_SIZE
) -> Optional[bytes]:
    """从 URL 下载 PDF 文件。

    支持：
    - 自动跟随重定向（最多 10 次）
    - 超时控制
    - 大小限制
    - Content-Type 验证

    Args:
        url: PDF 文件 URL
        timeout: 超时时间（秒）
        max_size: 最大文件大小（字节）

    Returns:
        PDF 二进制内容，失败返回 None
    """
    try:
        logger.info("开始下载 PDF: %s", url)

        headers = {
            'User-Agent': USER_AGENT,
            'Accept': 'application/pdf,*/*',
        }

        # 发送请求，允许重定向
        response = requests.get(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=True,
            stream=True  # 流式下载，便于控制大小
        )

        # 检查 HTTP 状态
        if response.status_code != 200:
            logger.warning(
                "下载失败: HTTP %d, URL: %s",
                response.status_code,
                url
            )
            return None

        # 检查 Content-Type（可能不准确，仅作参考）
        content_type = response.headers.get('Content-Type', '').lower()
        if content_type and 'pdf' not in content_type and 'octet-stream' not in content_type:
            logger.warning(
                "Content-Type 不是 PDF: %s, URL: %s",
                content_type,
                url
            )
            # 不直接返回，继续检查文件头

        # 检查 Content-Length
        content_length = response.headers.get('Content-Length')
        if content_length:
            size = int(content_length)
            if size > max_size:
                logger.warning(
                    "文件过大: %d bytes (限制 %d bytes), URL: %s",
                    size,
                    max_size,
                    url
                )
                return None

        # 分块下载，控制总大小
        chunks = []
        total_size = 0
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                chunks.append(chunk)
                total_size += len(chunk)
                if total_size > max_size:
                    logger.warning(
                        "下载超过大小限制: %d bytes, URL: %s",
                        total_size,
                        url
                    )
                    return None

        pdf_data = b''.join(chunks)

        # 验证 PDF 文件头
        if not is_valid_pdf(pdf_data):
            logger.warning(
                "下载内容不是有效 PDF (文件头验证失败), URL: %s",
                url
            )
            return None

        logger.info(
            "PDF 下载成功: %d bytes, URL: %s",
            len(pdf_data),
            url
        )
        return pdf_data

    except requests.exceptions.Timeout:
        logger.warning("下载超时 (%d 秒): %s", timeout, url)
        return None
    except requests.exceptions.TooManyRedirects:
        logger.warning("重定向次数过多: %s", url)
        return None
    except requests.exceptions.RequestException as e:
        logger.warning("下载出错: %s, URL: %s", e, url)
        return None
    except Exception as e:
        logger.error("下载 PDF 时发生未知错误: %s, URL: %s", e, url, exc_info=True)
        return None


def extract_pdfs_from_urls(
    text: str,
    timeout: int = DEFAULT_TIMEOUT
) -> List[Tuple[str, bytes]]:
    """从文本中提取 URL 并下载所有 PDF。

    这是一个便捷函数，组合了 URL 提取和 PDF 下载。

    Args:
        text: 邮件正文或任意文本
        timeout: 每个 URL 的下载超时时间（秒）

    Returns:
        成功下载的 PDF 列表: [(URL, 二进制内容), ...]
    """
    urls = extract_urls_from_text(text)
    if not urls:
        return []

    logger.info("发现 %d 个 URL，开始尝试下载 PDF", len(urls))

    pdfs = []
    for url in urls:
        pdf_data = download_pdf_from_url(url, timeout=timeout)
        if pdf_data:
            # 从 URL 中提取文件名，去除查询参数和非法字符
            from urllib.parse import urlparse, unquote

            parsed_url = urlparse(url)
            # 从路径中提取文件名（不包含查询参数）
            filename = parsed_url.path.split('/')[-1] or 'downloaded.pdf'
            # 解码 URL 编码（如 %20 -> 空格）
            filename = unquote(filename)
            # 移除文件名中的非法字符（Windows: <>:"/\|?*）
            filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
            # 确保文件名以 .pdf 结尾
            if not filename.lower().endswith('.pdf'):
                filename += '.pdf'
            pdfs.append((filename, pdf_data))

    logger.info("成功下载 %d 个 PDF", len(pdfs))
    return pdfs
