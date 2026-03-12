"""发票相关 API"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Optional
from datetime import datetime, timedelta
from bson import ObjectId
from pathlib import Path

from ..core.database import get_database
from ..models.user import User
from ..models.invoice import Invoice, InvoiceStats
from ..api.auth import get_current_user
from ..schemas.invoice import InvoiceResponse, InvoiceListResponse, InvoiceStatsResponse
from ..core.config import settings

router = APIRouter(prefix="/invoices", tags=["发票"])


@router.get("", response_model=InvoiceListResponse, response_model_by_alias=False)
async def get_invoices(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    invoice_type: Optional[str] = Query(None, description="发票类型"),
    project_name: Optional[str] = Query(None, description="发票项目"),
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    获取发票列表

    - 支持分页
    - 支持关键词搜索
    - 支持日期筛选
    - 支持类型筛选
    - 支持项目筛选
    """
    # 构建查询条件
    query = {"user_id": current_user.openid}

    # 关键词搜索
    if keyword:
        query["$or"] = [
            {"seller_name": {"$regex": keyword, "$options": "i"}},
            {"buyer_name": {"$regex": keyword, "$options": "i"}},
            {"invoice_number": {"$regex": keyword, "$options": "i"}},
        ]

    # 日期筛选
    if start_date or end_date:
        date_query = {}
        if start_date:
            date_query["$gte"] = start_date
        if end_date:
            date_query["$lte"] = end_date
        if date_query:
            query["invoice_date"] = date_query

    # 类型筛选
    if invoice_type:
        query["invoice_type"] = invoice_type

    # 项目筛选
    if project_name:
        query["project_name"] = project_name

    # 计算总数
    total = await db.invoices.count_documents(query)

    # 分页查询
    skip = (page - 1) * page_size
    cursor = db.invoices.find(query).sort("created_at", -1).skip(skip).limit(page_size)
    invoices = await cursor.to_list(length=page_size)

    # 转换 ObjectId 为字符串
    for invoice in invoices:
        invoice["_id"] = str(invoice["_id"])

    return InvoiceListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[InvoiceResponse(**invoice) for invoice in invoices]
    )


@router.get("/stats", response_model=InvoiceStatsResponse)
async def get_invoice_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    获取发票统计数据

    - 总数量和总金额
    - 本月数量和金额（按中国时区「本月」）
    - 已导出和待处理数量
    """
    # 本月日期范围（中国时区）：只统计「发票日期」在本月内的发票
    now_utc = datetime.utcnow()
    china_now = now_utc + timedelta(hours=8)
    month_start = china_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_start_str = month_start.strftime("%Y-%m-%d")
    # 下月 1 号（用于 invoice_date < 下月1日，即只算本月）
    if month_start.month == 12:
        next_month_start = month_start.replace(year=month_start.year + 1, month=1, day=1)
    else:
        next_month_start = month_start.replace(month=month_start.month + 1, day=1)
    month_end_exclusive = next_month_start.strftime("%Y-%m-%d")  # 如 "2025-04-01"

    # 金额聚合：兼容 total_amount 缺失或为字符串（先 ifNull 再转 double）
    amount_sum = {"$sum": {"$convert": {"input": {"$ifNull": ["$total_amount", 0]}, "to": "double", "onError": 0, "onNull": 0}}}

    # 总统计
    total_pipeline = [
        {"$match": {"user_id": current_user.openid}},
        {"$group": {
            "_id": None,
            "count": {"$sum": 1},
            "amount": amount_sum
        }}
    ]
    total_result = await db.invoices.aggregate(total_pipeline).to_list(1)
    total_count = total_result[0]["count"] if total_result else 0
    total_amount = float(total_result[0]["amount"]) if total_result else 0.0

    # 本月统计：仅当发票日期（invoice_date）在本月内才计入
    month_pipeline = [
        {"$match": {
            "user_id": current_user.openid,
            "invoice_date": {"$gte": month_start_str, "$lt": month_end_exclusive}
        }},
        {"$group": {
            "_id": None,
            "count": {"$sum": 1},
            "amount": amount_sum
        }}
    ]
    month_result = await db.invoices.aggregate(month_pipeline).to_list(1)
    month_count = month_result[0]["count"] if month_result else 0
    month_amount = float(month_result[0]["amount"]) if month_result else 0.0

    # 已导出数量
    exported_count = await db.invoices.count_documents({
        "user_id": current_user.openid,
        "is_exported": True
    })

    # 待处理数量（未导出）
    pending_count = total_count - exported_count

    return InvoiceStatsResponse(
        total_count=total_count,
        total_amount=round(total_amount, 2),
        month_count=month_count,
        month_amount=round(month_amount, 2),
        exported_count=exported_count,
        pending_count=pending_count
    )


@router.get("/{invoice_id}", response_model=InvoiceResponse, response_model_by_alias=False)
async def get_invoice_detail(
    invoice_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """获取发票详情"""
    if not ObjectId.is_valid(invoice_id):
        raise HTTPException(status_code=400, detail="无效的发票 ID")

    invoice_data = await db.invoices.find_one({
        "_id": ObjectId(invoice_id),
        "user_id": current_user.openid
    })

    if not invoice_data:
        raise HTTPException(status_code=404, detail="发票不存在")

    # 转换 ObjectId 为字符串
    invoice_data["_id"] = str(invoice_data["_id"])

    return InvoiceResponse(**invoice_data)


@router.post("/sync")
async def sync_invoices(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    手动同步邮箱发票

    立即触发一次邮箱检查，提取最新发票。
    注意：系统每 5 分钟会自动检查一次，无需频繁手动同步。
    """
    from ..services.email_service import EmailService

    email_service = EmailService(db)

    try:
        result = await email_service.process_user_emails(current_user)

        # 构建友好的提示消息
        success_count = result["success_count"]
        duplicate_count = result["duplicate_count"]
        duplicate_invoices = result["duplicate_invoices"]

        message_parts = []
        if success_count > 0:
            message_parts.append(f"成功同步 {success_count} 张发票")
        else:
            message_parts.append("未发现新发票")

        if duplicate_count > 0:
            message_parts.append(f"跳过 {duplicate_count} 张重复发票")

        return {
            "message": "，".join(message_parts),
            "success_count": success_count,
            "duplicate_count": duplicate_count,
            "duplicate_invoices": duplicate_invoices[:10]  # 最多返回10条重复信息
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"同步失败: {str(e)}")


@router.post("/{invoice_id}/export")
async def mark_invoice_exported(
    invoice_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """标记发票为已导出"""
    if not ObjectId.is_valid(invoice_id):
        raise HTTPException(status_code=400, detail="无效的发票 ID")

    result = await db.invoices.update_one(
        {"_id": ObjectId(invoice_id), "user_id": current_user.openid},
        {"$set": {"is_exported": True}}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="发票不存在")

    return {"message": "标记成功"}


@router.patch("/{invoice_id}")
async def update_invoice(
    invoice_id: str,
    project_name: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """更新发票信息（目前支持更新项目名称）"""
    if not ObjectId.is_valid(invoice_id):
        raise HTTPException(status_code=400, detail="无效的发票 ID")

    # 构建更新字段
    update_fields = {}
    if project_name is not None:
        update_fields["project_name"] = project_name

    if not update_fields:
        raise HTTPException(status_code=400, detail="没有需要更新的字段")

    # 更新发票
    result = await db.invoices.update_one(
        {"_id": ObjectId(invoice_id), "user_id": current_user.openid},
        {"$set": update_fields}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="发票不存在")

    return {"message": "更新成功"}


@router.get("/{invoice_id}/pdf")
async def download_invoice_pdf(
    invoice_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """下载发票PDF文件"""
    if not ObjectId.is_valid(invoice_id):
        raise HTTPException(status_code=400, detail="无效的发票 ID")

    # 查询发票信息
    invoice_data = await db.invoices.find_one({
        "_id": ObjectId(invoice_id),
        "user_id": current_user.openid
    })

    if not invoice_data:
        raise HTTPException(status_code=404, detail="发票不存在")

    pdf_path = invoice_data.get("pdf_path")
    if not pdf_path:
        raise HTTPException(status_code=404, detail="PDF文件不存在")

    # 构建完整的文件路径
    base_dir = Path(settings.INVOICE_STORAGE_PATH)
    full_path = base_dir / pdf_path

    if not full_path.exists():
        raise HTTPException(status_code=404, detail="PDF文件未找到")

    # 返回文件
    return FileResponse(
        path=str(full_path),
        media_type="application/pdf",
        filename=f"invoice_{invoice_data.get('invoice_number', 'unknown')}.pdf"
    )

