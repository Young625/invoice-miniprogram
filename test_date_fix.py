"""测试发票日期解析修复"""
import sys
from pathlib import Path

# 添加src路径
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from invoice_parser import InvoiceParser

# 尝试查找最新的PDF文件
data_dir = Path("data/invoices")
if not data_dir.exists():
    print(f"数据目录不存在: {data_dir}")
    exit(1)

pdfs = list(data_dir.rglob("*.pdf"))
if not pdfs:
    print("未找到任何PDF文件")
    exit(1)

# 使用最新的PDF文件
pdf_path = sorted(pdfs, key=lambda p: p.stat().st_mtime, reverse=True)[0]
print(f"找到 {len(pdfs)} 个PDF文件，使用最新的进行测试:")
print(f"  {pdf_path}")

print(f"\n解析PDF: {pdf_path.name}\n")

# 读取PDF内容
with open(pdf_path, 'rb') as f:
    pdf_data = f.read()

# 使用解析器解析
parser = InvoiceParser()
info = parser.parse(pdf_data)

print("=== 解析结果 ===\n")
print(f"发票类型: {info.invoice_type}")
print(f"发票号码: {info.invoice_number}")
print(f"开票日期: '{info.invoice_date}'")  # 重点检查
print(f"购买方: {info.buyer_name}")
print(f"销售方: {info.seller_name}")
print(f"价税合计: {info.total_amount}")

if info.invoice_date:
    print(f"\n✓ 日期解析成功: {info.invoice_date}")
else:
    print("\n✗ 日期解析失败")
