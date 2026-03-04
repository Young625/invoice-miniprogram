"""用户相关 API"""
from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime
import logging

from ..core.database import get_database
from ..models.user import User, EmailConfig
from ..api.auth import get_current_user

router = APIRouter(prefix="/user", tags=["用户"])
logger = logging.getLogger(__name__)

# 邮箱配置数量限制
MAX_EMAIL_CONFIGS = 3


@router.get("/email-configs")
async def get_email_configs(
    current_user: User = Depends(get_current_user)
):
    """获取所有邮箱配置"""
    return current_user.email_configs or []


@router.post("/email-configs")
async def add_email_config(
    config: EmailConfig,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    添加新邮箱配置

    最多支持 3 个邮箱配置
    """
    logger.info(f"用户 {current_user.openid} 尝试添加邮箱: {config.username}")

    # 获取当前用户的最新数据
    user_data = await db.users.find_one({"openid": current_user.openid})
    email_configs = user_data.get("email_configs", [])

    # 检查数量限制
    if len(email_configs) >= MAX_EMAIL_CONFIGS:
        raise HTTPException(
            status_code=400,
            detail=f"最多只能配置 {MAX_EMAIL_CONFIGS} 个邮箱"
        )

    # 检查当前用户是否已配置该邮箱
    for existing_config in email_configs:
        if existing_config.get("username") == config.username:
            raise HTTPException(
                status_code=400,
                detail="该邮箱已在您的配置列表中"
            )

    # 检查邮箱是否已被其他用户绑定
    existing_user = await db.users.find_one({
        "email_configs.username": config.username,
        "openid": {"$ne": current_user.openid}
    })

    if existing_user:
        logger.warning(f"邮箱 {config.username} 已被用户 {existing_user.get('openid')} 绑定")
        raise HTTPException(
            status_code=400,
            detail="该邮箱已被其他用户绑定"
        )

    # 添加新邮箱配置
    result = await db.users.update_one(
        {"openid": current_user.openid},
        {
            "$push": {"email_configs": config.model_dump()},
            "$set": {
                "updated_at": datetime.utcnow(),
                # 如果是第一个邮箱，同时更新 email 字段（兼容旧代码）
                **({"email": config.username} if len(email_configs) == 0 else {})
            }
        }
    )

    logger.info(f"用户 {current_user.openid} 邮箱配置添加成功")

    return {"message": "邮箱配置添加成功", "index": len(email_configs)}


@router.put("/email-configs/{index}")
async def update_email_config(
    index: int,
    config: EmailConfig,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    更新指定索引的邮箱配置
    """
    logger.info(f"用户 {current_user.openid} 尝试更新邮箱配置 {index}: {config.username}")

    # 获取当前用户的最新数据
    user_data = await db.users.find_one({"openid": current_user.openid})
    email_configs = user_data.get("email_configs", [])

    # 检查索引是否有效
    if index < 0 or index >= len(email_configs):
        raise HTTPException(
            status_code=400,
            detail="无效的邮箱配置索引"
        )

    # 如果邮箱地址改变了，需要检查新邮箱是否已被绑定
    old_username = email_configs[index].get("username")
    if old_username != config.username:
        # 检查当前用户的其他配置中是否已有该邮箱
        for i, existing_config in enumerate(email_configs):
            if i != index and existing_config.get("username") == config.username:
                raise HTTPException(
                    status_code=400,
                    detail="该邮箱已在您的配置列表中"
                )

        # 检查邮箱是否已被其他用户绑定
        existing_user = await db.users.find_one({
            "email_configs.username": config.username,
            "openid": {"$ne": current_user.openid}
        })

        if existing_user:
            logger.warning(f"邮箱 {config.username} 已被用户 {existing_user.get('openid')} 绑定")
            raise HTTPException(
                status_code=400,
                detail="该邮箱已被其他用户绑定"
            )

    # 更新邮箱配置
    result = await db.users.update_one(
        {"openid": current_user.openid},
        {
            "$set": {
                f"email_configs.{index}": config.model_dump(),
                "updated_at": datetime.utcnow()
            }
        }
    )

    logger.info(f"用户 {current_user.openid} 邮箱配置 {index} 更新成功")

    return {"message": "邮箱配置更新成功"}


@router.delete("/email-configs/{index}")
async def delete_email_config(
    index: int,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """删除指定索引的邮箱配置"""
    logger.info(f"用户 {current_user.openid} 尝试删除邮箱配置 {index}")

    # 获取当前用户的最新数据
    user_data = await db.users.find_one({"openid": current_user.openid})
    email_configs = user_data.get("email_configs", [])

    # 检查索引是否有效
    if index < 0 or index >= len(email_configs):
        raise HTTPException(
            status_code=400,
            detail="无效的邮箱配置索引"
        )

    # 删除指定索引的配置
    email_configs.pop(index)

    # 构建更新数据
    update_data = {
        "email_configs": email_configs,
        "updated_at": datetime.utcnow()
    }

    # 如果删除后还有邮箱，更新 email 字段为第一个邮箱
    # 如果删除后没有邮箱了，清空 email 字段
    if len(email_configs) > 0:
        update_data["email"] = email_configs[0].get("username")
    else:
        update_data["email"] = None

    result = await db.users.update_one(
        {"openid": current_user.openid},
        {"$set": update_data}
    )

    logger.info(f"用户 {current_user.openid} 邮箱配置 {index} 删除成功")

    return {"message": "邮箱配置已删除"}


@router.put("/email-configs/set-primary/{index}")
async def set_primary_email(
    index: int,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    设置主邮箱

    将指定索引的邮箱设置为主邮箱（移动到第一位）
    """
    logger.info(f"用户 {current_user.openid} 尝试设置主邮箱为索引 {index}")

    # 获取当前用户的最新数据
    user_data = await db.users.find_one({"openid": current_user.openid})
    email_configs = user_data.get("email_configs", [])

    # 检查索引是否有效
    if index < 0 or index >= len(email_configs):
        raise HTTPException(
            status_code=400,
            detail="无效的邮箱配置索引"
        )

    # 如果已经是主邮箱，无需操作
    if index == 0:
        return {"message": "该邮箱已经是主邮箱"}

    # 将指定邮箱移到第一位
    selected_config = email_configs.pop(index)
    email_configs.insert(0, selected_config)

    # 更新数据库
    result = await db.users.update_one(
        {"openid": current_user.openid},
        {
            "$set": {
                "email_configs": email_configs,
                "email": selected_config.get("username"),  # 更新主邮箱地址
                "updated_at": datetime.utcnow()
            }
        }
    )

    logger.info(f"用户 {current_user.openid} 主邮箱设置成功: {selected_config.get('username')}")

    return {"message": "主邮箱设置成功", "primary_email": selected_config.get("username")}
