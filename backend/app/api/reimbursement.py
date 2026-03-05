"""报销包相关 API"""
from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import Response
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List
from bson import ObjectId

from ..core.database import get_database
from ..models.user import User
from ..api.auth import get_current_user
from ..services.reimbursement_service import ReimbursementService
from pydantic import BaseModel

router = APIRouter(prefix="/reimbursement", tags=["报销"])


class ReimbursementRequest(BaseModel):
    """报销包生成请求"""
    invoice_ids: List[str]
    name: str = None
    department: str = None
    reason: str = None


@router.post("/generate")
async def generate_reimbursement_package(
    request: ReimbursementRequest = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    生成报销包

    包含：
    1. 发票汇总表（Excel）
    2. 报销单（PDF）
    3. 发票原件（PDF打包）

    返回 ZIP 文件
    """
    if not request.invoice_ids:
        raise HTTPException(status_code=400, detail="请选择至少一张发票")

    # 获取发票数据
    invoice_object_ids = []
    for invoice_id in request.invoice_ids:
        if not ObjectId.is_valid(invoice_id):
            raise HTTPException(status_code=400, detail=f"无效的发票 ID: {invoice_id}")
        invoice_object_ids.append(ObjectId(invoice_id))

    cursor = db.invoices.find({
        "_id": {"$in": invoice_object_ids},
        "user_id": current_user.openid
    })
    invoices = await cursor.to_list(length=len(invoice_object_ids))

    if not invoices:
        raise HTTPException(status_code=404, detail="未找到发票")

    # 转换 ObjectId 为字符串
    for invoice in invoices:
        invoice["_id"] = str(invoice["_id"])

    # 生成报销包
    service = ReimbursementService()
    user_info = {
        "name": request.name,
        "department": request.department,
        "reason": request.reason
    }

    try:
        from ..core.config import settings
        from pathlib import Path

        # 使用配置中的存储路径
        pdf_base_dir = Path(settings.INVOICE_STORAGE_PATH).resolve()

        zip_data = service.create_reimbursement_package(
            invoices=invoices,
            user_info=user_info,
            pdf_dir=str(pdf_base_dir)
        )

        # 返回 ZIP 文件
        from datetime import datetime
        from urllib.parse import quote

        filename = f"报销包_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        # URL 编码中文文件名
        encoded_filename = quote(filename)

        return Response(
            content=zip_data,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成报销包失败: {str(e)}")
