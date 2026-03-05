"""验证数据迁移结果"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

async def verify_migration():
    """验证数据迁移结果"""

    # 连接数据库
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.MONGODB_DB_NAME]

    print("=" * 60)
    print("验证数据迁移结果")
    print("=" * 60)

    # 统计各种情况的发票数量
    total_count = await db.invoices.count_documents({})
    has_project_name = await db.invoices.count_documents({"project_name": {"$ne": None, "$ne": ""}})
    no_project_name = await db.invoices.count_documents({
        "$or": [
            {"project_name": {"$exists": False}},
            {"project_name": None},
            {"project_name": ""}
        ]
    })

    print(f"\n总发票数: {total_count}")
    print(f"有 project_name: {has_project_name}")
    print(f"无 project_name: {no_project_name}")

    # 获取所有唯一的项目名称
    pipeline = [
        {"$match": {"project_name": {"$ne": None, "$ne": ""}}},
        {"$group": {"_id": "$project_name", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]

    project_stats = await db.invoices.aggregate(pipeline).to_list(length=None)

    print("\n项目名称统计:")
    print("-" * 60)
    for stat in project_stats:
        print(f"  {stat['_id']}: {stat['count']} 张发票")

    # 显示几个示例
    print("\n发票示例:")
    print("-" * 60)
    cursor = db.invoices.find({"project_name": {"$ne": None}}).limit(3)
    invoices = await cursor.to_list(length=3)

    for invoice in invoices:
        print(f"\n发票号: {invoice.get('invoice_number', 'N/A')}")
        print(f"  销售方: {invoice.get('seller_name', 'N/A')}")
        print(f"  项目名称: {invoice.get('project_name', 'N/A')}")
        print(f"  商品列表: {invoice.get('items', [])}")

    print("\n" + "=" * 60)
    print("✅ 验证完成")
    print("=" * 60)

    # 关闭数据库连接
    client.close()

if __name__ == "__main__":
    asyncio.run(verify_migration())
