"""认证相关的数据模式"""
from pydantic import BaseModel
from typing import Optional


class LoginRequest(BaseModel):
    """登录请求"""
    code: str  # 微信登录 code
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None


class UserProfile(BaseModel):
    """用户信息"""
    openid: str
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    email: Optional[str] = None


class LoginResponse(BaseModel):
    """登录响应"""
    access_token: str
    token_type: str
    user: UserProfile
