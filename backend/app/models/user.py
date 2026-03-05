"""用户数据模型"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr
from bson import ObjectId


class PyObjectId(ObjectId):
    """MongoDB ObjectId 类型"""
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        from pydantic_core import core_schema
        return core_schema.union_schema([
            core_schema.is_instance_schema(ObjectId),
            core_schema.chain_schema([
                core_schema.str_schema(),
                core_schema.no_info_plain_validator_function(cls.validate),
            ])
        ], serialization=core_schema.plain_serializer_function_ser_schema(str))

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)


class EmailConfig(BaseModel):
    """邮箱配置"""
    imap_server: str
    imap_port: int = 993
    username: str
    auth_code: str  # 授权码
    folder: str = "INBOX"


class User(BaseModel):
    """用户模型"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    openid: str  # 微信 openid
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    email_configs: List[EmailConfig] = Field(default_factory=list)  # 支持多个邮箱
    auto_sync_enabled: Optional[bool] = False  # 是否启用自动同步（默认关闭，需用户主动开启）
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        json_schema_extra = {
            "example": {
                "openid": "oxxxxxxxxxxxxxx",
                "nickname": "张三",
                "email": "user@example.com"
            }
        }
