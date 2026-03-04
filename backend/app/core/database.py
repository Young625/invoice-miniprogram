"""数据库连接"""
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional
from .config import settings

class Database:
    client: Optional[AsyncIOMotorClient] = None

    @classmethod
    async def connect_db(cls):
        """连接数据库"""
        cls.client = AsyncIOMotorClient(settings.MONGODB_URL)
        print(f"✅ 已连接到 MongoDB: {settings.MONGODB_URL}")

    @classmethod
    async def close_db(cls):
        """关闭数据库连接"""
        if cls.client:
            cls.client.close()
            print("✅ 已关闭 MongoDB 连接")

    @classmethod
    def get_db(cls):
        """获取数据库实例"""
        if not cls.client:
            raise Exception("数据库未连接")
        return cls.client[settings.MONGODB_DB_NAME]


# 便捷函数
async def get_database():
    """依赖注入：获取数据库"""
    return Database.get_db()
