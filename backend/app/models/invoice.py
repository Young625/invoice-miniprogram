"""发票数据模型"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from bson import ObjectId
from .user import PyObjectId


class Invoice(BaseModel):
    """发票模型"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    user_id: str  # 用户 ID

    # 发票基本信息
    invoice_type: Optional[str] = None  # 发票类型
    invoice_code: Optional[str] = None  # 发票代码
    invoice_number: Optional[str] = None  # 发票号码
    invoice_date: Optional[str] = None  # 开票日期

    # 购买方信息
    buyer_name: Optional[str] = None
    buyer_tax_id: Optional[str] = None

    # 销售方信息
    seller_name: Optional[str] = None
    seller_tax_id: Optional[str] = None

    # 金额信息
    amount: Optional[float] = None  # 金额
    tax_amount: Optional[float] = None  # 税额
    tax_rate: Optional[float] = None  # 税率（如：13、9、6、3，不含税为0）
    total_amount: Optional[float] = None  # 价税合计（铁路发票的退票费/改签费也存在此字段）

    # 商品信息
    items: List[str] = []  # 商品名称列表
    project_name: Optional[str] = None  # 发票项目名称（从items中提取的主要项目）

    # 来源信息
    email_subject: Optional[str] = None  # 邮件主题
    email_uid: Optional[str] = None  # 邮件唯一标识（用于去重）
    source_type: str = "attachment"  # attachment 或 link
    pdf_path: Optional[str] = None  # PDF 文件路径

    # 时间戳
    extracted_at: datetime = Field(default_factory=datetime.utcnow)  # 提取时间
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # 状态
    is_valid: bool = True  # 是否有效
    is_exported: bool = False  # 是否已导出

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        json_schema_extra = {
            "example": {
                "invoice_type": "增值税电子普通发票",
                "invoice_number": "12345678",
                "invoice_date": "2024-02-28",
                "seller_name": "中国移动",
                "total_amount": 128.00
            }
        }


class InvoiceStats(BaseModel):
    """发票统计"""
    total_count: int = 0  # 总数量
    total_amount: float = 0.0  # 总金额
    month_count: int = 0  # 本月数量
    month_amount: float = 0.0  # 本月金额
    exported_count: int = 0  # 已导出数量
    pending_count: int = 0  # 待处理数量
