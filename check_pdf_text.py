"""检查PDF中的日期文本编码"""
import sys
from pathlib import Path
import pdfplumber

# 添加src路径
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# 使用最新的PDF
data_dir = Path("data/invoices")
pdfs = sorted(list(data_dir.rglob("*.pdf")), key=lambda p: p.stat().st_mtime, reverse=True)
pdf_path = pdfs[0]

print(f"检查PDF: {pdf_path.name}\n")

with pdfplumber.open(pdf_path) as pdf:
    text = pdf.pages[0].extract_text()

    # 查找包含"日期"的行
    print("=== 包含'日期'的文本行 ===\n")
    for line in text.split('\n'):
        if '日期' in line:
            print(f"文本: {line}")
            print(f"字节: {line.encode('unicode_escape').decode('ascii')}")

            # 检查特殊字符
            if '⽉' in line:
                print("  ✓ 包含 Kangxi 月 (U+2F49)")
            if '⽇' in line:
                print("  ✓ 包含 Kangxi 日 (U+2F47)")
            if '月' in line:
                print("  ✓ 包含 正常 月 (U+6708)")
            if '日' in line:
                print("  ✓ 包含 正常 日 (U+65E5)")
            print()
