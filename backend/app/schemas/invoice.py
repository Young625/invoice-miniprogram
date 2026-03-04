"""发票相关的数据模式"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class InvoiceResponse(BaseModel):
    """发票响应"""
    id: str = Field(alias="_id")
    invoice_type: Optional[str] = None
    invoice_code: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    buyer_name: Optional[str] = None
    buyer_tax_id: Optional[str] = None
    seller_name: Optional[str] = None
    seller_tax_id: Optional[str] = None
    amount: Optional[float] = None
    tax_amount: Optional[float] = None
    total_amount: Optional[float] = None
    items: List[str] = []
    email_subject: Optional[str] = None
    source_type: str = "attachment"
    pdf_path: Optional[str] = None
    extracted_at: datetime
    is_exported: bool = False

    class Config:
        from_attributes = True
        populate_by_name = True
        # 关键配置：序列化时使用字段名而不是别名
        by_alias = False


class InvoiceListResponse(BaseModel):
    """发票列表响应"""
    total: int
    page: int
    page_size: int
    items: List[InvoiceResponse]


class InvoiceStatsResponse(BaseModel):
    """发票统计响应"""
    total_count: int
    total_amount: float
    month_count: int
    month_amount: float
    exported_count: int
    pending_count: int
