"""认证相关 API"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import timedelta, datetime
from typing import Optional
import logging

from ..core.database import get_database
from ..core.security import create_access_token, decode_access_token
from ..core.config import settings
from ..models.user import User
from ..schemas.auth import LoginRequest, LoginResponse, UserProfile
from ..services.wechat_service import WeChatService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["认证"])
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncIOMotorDatabase = Depends(get_database)
) -> User:
    """获取当前用户（依赖注入）"""
    token = credentials.credentials
    payload = decode_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证"
        )

    openid = payload.get("sub")
    if not openid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证"
        )

    user_data = await db.users.find_one({"openid": openid})
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    return User(**user_data)


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    微信登录

    - 使用微信 code 换取 openid
    - 如果用户不存在则自动注册
    - 返回 JWT token
    """
    # 打印接收到的请求数据
    logger.info(f"收到登录请求: code={request.code}, nickname={request.nickname}, avatar_url={request.avatar_url}")

    # 检查微信配置
    if not settings.WECHAT_APP_ID or not settings.WECHAT_APP_SECRET:
        # 开发模式：使用 code 作为 openid（仅用于测试）
        logger.warning("微信配置未设置，使用开发模式")
        openid = f"dev_{request.code}"
    else:
        # 生产模式：调用微信 API 获取 openid
        wechat_service = WeChatService(settings.WECHAT_APP_ID, settings.WECHAT_APP_SECRET)
        session_data = await wechat_service.code_to_session(request.code)

        if not session_data or not session_data.get("openid"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="微信登录失败，请重试"
            )

        openid = session_data["openid"]
        logger.info(f"用户登录: openid={openid}")

    # 查找或创建用户
    user_data = await db.users.find_one({"openid": openid})

    if not user_data:
        # 新用户，自动注册
        logger.info(f"创建新用户: openid={openid}, nickname={request.nickname}, avatar_url={request.avatar_url}")
        new_user = User(
            openid=openid,
            nickname=request.nickname or "微信用户",
            avatar_url=request.avatar_url or ""
        )
        result = await db.users.insert_one(new_user.model_dump(by_alias=True, exclude=["id"]))
        user_data = await db.users.find_one({"_id": result.inserted_id})
        logger.info(f"新用户创建成功: {user_data}")
    else:
        # 已存在用户，不更新昵称和头像（用户可能已经自定义过）
        logger.info(f"用户已存在: openid={openid}，保留用户自定义信息")
        # 只更新最后登录时间
        await db.users.update_one(
            {"openid": openid},
            {"$set": {"updated_at": datetime.utcnow()}}
        )
        user_data = await db.users.find_one({"openid": openid})

    user = User(**user_data)

    # 创建 token
    access_token = create_access_token(
        data={"sub": user.openid},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserProfile(
            openid=user.openid,
            nickname=user.nickname,
            avatar_url=user.avatar_url,
            email=user.email
        )
    )


@router.get("/profile", response_model=UserProfile)
async def get_profile(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return UserProfile(
        openid=current_user.openid,
        nickname=current_user.nickname,
        avatar_url=current_user.avatar_url,
        email=current_user.email
    )


@router.put("/profile", response_model=UserProfile)
async def update_profile(
    request: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """更新用户信息"""
    update_data = {}

    # 更新昵称
    if "nickname" in request and request["nickname"]:
        update_data["nickname"] = request["nickname"]

    # 更新头像
    if "avatar_url" in request and request["avatar_url"]:
        update_data["avatar_url"] = request["avatar_url"]

    # 更新邮箱
    if "email" in request and request["email"]:
        update_data["email"] = request["email"]

    if update_data:
        logger.info(f"更新用户 {current_user.openid} 的信息: {update_data}")
        await db.users.update_one(
            {"openid": current_user.openid},
            {"$set": update_data}
        )

        # 获取更新后的用户信息
        updated_user_data = await db.users.find_one({"openid": current_user.openid})
        updated_user = User(**updated_user_data)

        return UserProfile(
            openid=updated_user.openid,
            nickname=updated_user.nickname,
            avatar_url=updated_user.avatar_url,
            email=updated_user.email
        )

    # 如果没有更新数据，返回当前用户信息
    return UserProfile(
        openid=current_user.openid,
        nickname=current_user.nickname,
        avatar_url=current_user.avatar_url,
        email=current_user.email
    )
