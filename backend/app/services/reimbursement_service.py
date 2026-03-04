"""报销包生成服务：Excel汇总表 + 报销单PDF + 发票原件打包"""
import os
import io
import zipfile
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors

import logging

logger = logging.getLogger(__name__)


class ReimbursementService:
    """报销包生成服务"""

    def __init__(self):
        # 注册中文字体（支持多平台）
        self.font_name = 'SimSun'  # 默认字体名
        try:
            # 尝试多个字体路径
            font_paths = [
                # Linux 常见字体路径
                "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
                "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/arphic/uming.ttc",
                # Windows 字体路径
                "C:/Windows/Fonts/simhei.ttf",
                "C:/Windows/Fonts/simsun.ttc",
                # macOS 字体路径
                "/System/Library/Fonts/PingFang.ttc",
                "/System/Library/Fonts/STHeiti Light.ttc",
            ]

            font_registered = False
            for font_path in font_paths:
                if os.path.exists(font_path):
                    try:
                        pdfmetrics.registerFont(TTFont('ChineseFont', font_path))
                        self.font_name = 'ChineseFont'
                        font_registered = True
                        logger.info(f"成功注册中文字体: {font_path}")
                        break
                    except Exception as e:
                        logger.warning(f"注册字体失败 {font_path}: {e}")
                        continue

            if not font_registered:
                logger.warning("未找到中文字体，将使用默认字体（可能无法显示中文）")

        except Exception as e:
            logger.error(f"字体注册过程出错: {e}")

    def generate_excel_summary(self, invoices: List[Dict[str, Any]]) -> bytes:
        """
        生成发票汇总表 Excel

        Args:
            invoices: 发票列表

        Returns:
            Excel 文件的字节内容
        """
        wb = Workbook()
        ws = wb.active
        ws.title = "发票汇总表"

        # 设置列宽
        ws.column_dimensions['A'].width = 8
        ws.column_dimensions['B'].width = 20
        ws.column_dimensions['C'].width = 18
        ws.column_dimensions['D'].width = 25
        ws.column_dimensions['E'].width = 15
        ws.column_dimensions['F'].width = 30
        ws.column_dimensions['G'].width = 30
        ws.column_dimensions['H'].width = 15

        # 标题样式
        title_font = Font(name='Arial', size=14, bold=True)
        title_fill = PatternFill(start_color="1989FA", end_color="1989FA", fill_type="solid")
        title_alignment = Alignment(horizontal='center', vertical='center')

        # 边框样式
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )

        # 表头
        headers = ['序号', '发票类型', '发票代码', '发票号码', '开票日期', '购买方名称', '销售方名称', '金额（元）']
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num, value=header)
            cell.font = title_font
            cell.fill = title_fill
            cell.alignment = title_alignment
            cell.border = thin_border

        # 数据行
        total_amount = 0
        for row_num, invoice in enumerate(invoices, 2):
            ws.cell(row=row_num, column=1, value=row_num - 1).border = thin_border
            ws.cell(row=row_num, column=2, value=invoice.get('invoice_type', '')).border = thin_border
            ws.cell(row=row_num, column=3, value=invoice.get('invoice_code', '')).border = thin_border
            ws.cell(row=row_num, column=4, value=invoice.get('invoice_number', '')).border = thin_border
            ws.cell(row=row_num, column=5, value=invoice.get('invoice_date', '')).border = thin_border
            ws.cell(row=row_num, column=6, value=invoice.get('buyer_name', '')).border = thin_border
            ws.cell(row=row_num, column=7, value=invoice.get('seller_name', '')).border = thin_border

            amount = invoice.get('total_amount', 0) or 0
            ws.cell(row=row_num, column=8, value=amount).border = thin_border
            total_amount += amount

        # 合计行
        summary_row = len(invoices) + 2
        ws.cell(row=summary_row, column=7, value='合计：').font = Font(bold=True)
        ws.cell(row=summary_row, column=8, value=total_amount).font = Font(bold=True, color="FF0000")

        # 保存到字节流
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output.getvalue()

    def generate_reimbursement_pdf(
        self,
        invoices: List[Dict[str, Any]],
        user_info: Dict[str, Any]
    ) -> bytes:
        """
        生成报销单 PDF

        Args:
            invoices: 发票列表
            user_info: 用户信息（报销人、部门、事由等）

        Returns:
            PDF 文件的字节内容
        """
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        try:
            # 使用中文字体
            c.setFont(self.font_name, 12)
        except:
            # 如果中文字体不可用，使用默认字体
            c.setFont('Helvetica', 12)
            logger.warning("使用默认字体，中文可能无法正常显示")

        # 标题
        try:
            c.setFont(self.font_name, 20)
        except:
            c.setFont('Helvetica-Bold', 20)
        c.drawCentredString(width / 2, height - 2 * cm, "费用报销单")

        # 报销信息
        y_position = height - 4 * cm
        try:
            c.setFont(self.font_name, 12)
        except:
            c.setFont('Helvetica', 12)

        # 报销人信息
        reimbursement_no = f"BX{datetime.now().strftime('%Y%m%d%H%M%S')}"
        c.drawString(3 * cm, y_position, f"报销人: {user_info.get('name', '未填写')}")
        c.drawString(10 * cm, y_position, f"部门: {user_info.get('department', '未填写')}")

        y_position -= 1 * cm
        c.drawString(3 * cm, y_position, f"日期: {datetime.now().strftime('%Y-%m-%d')}")
        c.drawString(10 * cm, y_position, f"单号: {reimbursement_no}")

        # 报销明细表
        y_position -= 2 * cm
        try:
            c.setFont(self.font_name, 12)
        except:
            c.setFont('Helvetica-Bold', 12)
        c.drawString(3 * cm, y_position, "报销明细:")

        # 表头
        y_position -= 0.8 * cm
        try:
            c.setFont(self.font_name, 10)
        except:
            c.setFont('Helvetica', 10)
        c.drawString(3 * cm, y_position, "序号")
        c.drawString(5 * cm, y_position, "发票号码")
        c.drawString(10 * cm, y_position, "金额（元）")
        c.drawString(14 * cm, y_position, "日期")

        # 画线
        c.line(2.5 * cm, y_position - 0.2 * cm, width - 2.5 * cm, y_position - 0.2 * cm)

        # 明细数据
        total_amount = 0
        for idx, invoice in enumerate(invoices, 1):
            y_position -= 0.8 * cm
            if y_position < 5 * cm:  # 换页
                c.showPage()
                y_position = height - 3 * cm
                try:
                    c.setFont(self.font_name, 10)
                except:
                    c.setFont('Helvetica', 10)

            c.drawString(3 * cm, y_position, str(idx))
            c.drawString(5 * cm, y_position, invoice.get('invoice_number', '')[:15])
            amount = invoice.get('total_amount', 0) or 0
            c.drawString(10 * cm, y_position, f"{amount:.2f}")
            c.drawString(14 * cm, y_position, invoice.get('invoice_date', ''))
            total_amount += amount

        # 合计
        y_position -= 1 * cm
        c.line(2.5 * cm, y_position, width - 2.5 * cm, y_position)
        y_position -= 0.8 * cm
        try:
            c.setFont(self.font_name, 12)
        except:
            c.setFont('Helvetica-Bold', 12)
        c.drawString(8 * cm, y_position, f"合计金额: ¥{total_amount:.2f}")

        # 报销事由
        y_position -= 2 * cm
        try:
            c.setFont(self.font_name, 12)
        except:
            c.setFont('Helvetica', 12)
        c.drawString(3 * cm, y_position, f"报销事由: {user_info.get('reason', '业务费用报销')}")

        # 签字栏
        y_position -= 3 * cm
        c.drawString(3 * cm, y_position, "报销人签字: _____________")
        c.drawString(10 * cm, y_position, "日期: _____________")

        y_position -= 1 * cm
        c.drawString(3 * cm, y_position, "部门主管: _____________")
        c.drawString(10 * cm, y_position, "日期: _____________")

        y_position -= 1 * cm
        c.drawString(3 * cm, y_position, "财务审核: _____________")
        c.drawString(10 * cm, y_position, "日期: _____________")

        c.save()
        buffer.seek(0)
        return buffer.getvalue()

    def create_reimbursement_package(
        self,
        invoices: List[Dict[str, Any]],
        user_info: Dict[str, Any],
        pdf_dir: str
    ) -> bytes:
        """
        创建完整的报销包（ZIP文件）

        Args:
            invoices: 发票列表
            user_info: 用户信息
            pdf_dir: 发票PDF文件存储目录

        Returns:
            ZIP 文件的字节内容
        """
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # 1. 添加 Excel 汇总表
            excel_data = self.generate_excel_summary(invoices)
            zip_file.writestr('发票汇总表.xlsx', excel_data)
            logger.info("已添加 Excel 汇总表")

            # 2. 添加报销单 PDF
            pdf_data = self.generate_reimbursement_pdf(invoices, user_info)
            zip_file.writestr('报销单.pdf', pdf_data)
            logger.info("已添加报销单 PDF")

            # 3. 添加发票原件 PDF
            pdf_count = 0
            for idx, invoice in enumerate(invoices, 1):
                pdf_path = invoice.get('pdf_path')
                if pdf_path:
                    # 将路径分隔符统一转换为当前系统的分隔符
                    # 数据库中可能存储的是Windows风格的路径（使用\）
                    pdf_path = pdf_path.replace('\\', os.sep).replace('/', os.sep)

                    # 拼接完整路径
                    full_pdf_path = os.path.join(pdf_dir, pdf_path)

                    logger.info(f"尝试读取PDF: {full_pdf_path}")
                    full_pdf_path = os.path.join(pdf_dir, pdf_path)

                    if os.path.exists(full_pdf_path):
                        try:
                            with open(full_pdf_path, 'rb') as f:
                                pdf_content = f.read()
                            # 使用序号和发票号码命名
                            invoice_number = invoice.get('invoice_number', 'unknown')
                            filename = f"{idx:02d}_{invoice_number}.pdf"
                            zip_file.writestr(f'发票原件/{filename}', pdf_content)
                            pdf_count += 1
                            logger.info(f"已添加发票原件: {filename}")
                        except Exception as e:
                            logger.error(f"添加发票 PDF 失败: {full_pdf_path}, {e}")
                    else:
                        logger.warning(f"发票 PDF 文件不存在: {full_pdf_path}")
                else:
                    logger.warning(f"发票 {invoice.get('invoice_number')} 没有 PDF 路径")

            logger.info(f"已添加 {pdf_count}/{len(invoices)} 个发票原件 PDF")

        zip_buffer.seek(0)
        return zip_buffer.getvalue()
