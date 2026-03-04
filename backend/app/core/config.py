"""配置文件"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """应用配置"""

    # 应用信息
    APP_NAME: str = "发票管理系统"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # API 配置
    API_PREFIX: str = "/api"

    # MongoDB 配置
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "invoice_db"

    # JWT 配置
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 天

    # 微信小程序配置（后续填入）
    WECHAT_APP_ID: Optional[str] = None
    WECHAT_APP_SECRET: Optional[str] = None

    # 文件存储路径
    INVOICE_STORAGE_PATH: str = "../data/invoices"
    EXCEL_OUTPUT_PATH: str = "../data/output"

    # 邮箱轮询配置
    EMAIL_POLL_INTERVAL: int = 300  # 5 分钟

    # CORS 配置
    CORS_ORIGINS: list = [
        "http://localhost",
        "http://localhost:8080",
        "https://servicewechat.com",  # 微信小程序域名
    ]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
