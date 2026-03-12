"""用户相关 API"""
from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime
import logging
import imaplib
import ssl
import asyncio

from ..core.database import get_database
from ..models.user import User, EmailConfig
from ..api.auth import get_current_user

router = APIRouter(prefix="/user", tags=["用户"])
logger = logging.getLogger(__name__)

# 邮箱配置数量限制
MAX_EMAIL_CONFIGS = 3


def _verify_imap_connection(config: EmailConfig) -> None:
    """
    尝试 IMAP 连接验证邮箱配置是否正确。
    连接失败时抛出 HTTPException。
    """
    try:
        ctx = ssl.create_default_context()
        with imaplib.IMAP4_SSL(config.imap_server, config.imap_port, ssl_context=ctx) as conn:
            conn.login(config.username, config.auth_code)
    except imaplib.IMAP4.error as e:
        # 所有 IMAP 错误都统一处理，不暴露技术细节
        logger.error(f"IMAP 登录失败: {str(e)}")

        # 根据邮箱类型给出不同的提示
        if config.email_type == "custom":
            raise HTTPException(
                status_code=400,
                detail="邮箱验证失败，请检查邮箱账号、授权码或IMAP服务器配置是否正确"
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="邮箱验证失败，请检查邮箱账号或授权码是否正确"
            )
    except (OSError, ConnectionRefusedError, TimeoutError) as e:
        logger.error(f"连接邮箱服务器失败: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"无法连接到邮箱服务器，请检查网络连接或IMAP服务器配置"
        )
    except Exception as e:
        logger.error(f"邮箱验证异常: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail="邮箱验证失败，请检查配置是否正确"
        )


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

    # 验证 IMAP 连接（确认账号和授权码正确）
    logger.info(f"验证邮箱 IMAP 连接: {config.username}")
    await asyncio.get_event_loop().run_in_executor(None, _verify_imap_connection, config)
    logger.info(f"邮箱 {config.username} IMAP 验证通过")

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

    # 验证 IMAP 连接（确认账号和授权码正确）
    logger.info(f"验证邮箱 IMAP 连接: {config.username}")
    await asyncio.get_event_loop().run_in_executor(None, _verify_imap_connection, config)
    logger.info(f"邮箱 {config.username} IMAP 验证通过")

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


@router.get("/auto-sync-status")
async def get_auto_sync_status(
    current_user: User = Depends(get_current_user)
):
    """获取自动同步状态"""
    # 如果 auto_sync_enabled 为 None，则返回 False
    enabled = current_user.auto_sync_enabled if current_user.auto_sync_enabled is not None else False
    return {"auto_sync_enabled": enabled}


@router.put("/auto-sync-status")
async def update_auto_sync_status(
    request_data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """更新自动同步状态"""
    enabled = request_data.get("enabled", False)
    logger.info(f"用户 {current_user.openid} 更新自动同步状态: {enabled}")

    result = await db.users.update_one(
        {"openid": current_user.openid},
        {
            "$set": {
                "auto_sync_enabled": enabled,
                "updated_at": datetime.utcnow()
            }
        }
    )

    logger.info(f"用户 {current_user.openid} 自动同步状态更新成功")

    return {"message": "自动同步状态已更新", "auto_sync_enabled": enabled}
