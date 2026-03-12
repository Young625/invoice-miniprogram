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

        # 创建索引
        await cls._create_indexes()

    @classmethod
    async def _create_indexes(cls):
        """创建数据库索引"""
        db = cls.get_db()

        # 删除所有与 invoice_number 相关的旧唯一索引（如果存在）
        # 不再使用数据库层面的唯一索引，改为应用层控制
        try:
            existing_indexes = await db.invoices.index_information()
            print(f"📋 现有索引: {list(existing_indexes.keys())}")
            for index_name in existing_indexes:
                if "invoice_number" in index_name and index_name != "_id_":
                    await db.invoices.drop_index(index_name)
                    print(f"✅ 已删除旧索引: {index_name}")
        except Exception as e:
            print(f"⚠️  删除旧索引时出错: {e}")

        # 创建普通索引（非唯一）以提升查询性能
        try:
            await db.invoices.create_index(
                "invoice_number",
                name="invoice_number_index"
            )
            print("✅ 已创建发票号码索引（非唯一，用于提升查询性能）")
        except Exception as e:
            if "already exists" in str(e):
                print("⚠️  发票号码索引已存在")
            else:
                print(f"⚠️  创建索引时出错: {e}")

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
