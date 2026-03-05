"""更新数据库：将不在固定列表中的项目归类为"其他" """
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

# 固定的项目列表
FIXED_PROJECTS = [
    '餐饮服务', '运输服务', '住宿服务', '办公用品',
    '金融服务', '通讯服务', '会议服务', '培训服务',
    '咨询服务', '租赁服务', '维修服务'
]

async def update_project_names():
    """更新项目名称：不在固定列表中的归类为"其他" """

    # 连接数据库
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.MONGODB_DB_NAME]

    print("=" * 60)
    print("更新项目名称：将不在固定列表中的归类为'其他'")
    print("=" * 60)

    # 查询所有发票
    total_count = await db.invoices.count_documents({})
    print(f"\n数据库中共有 {total_count} 张发票")

    # 获取所有发票
    cursor = db.invoices.find({})
    invoices = await cursor.to_list(length=None)

    updated_count = 0
    unchanged_count = 0

    print("\n开始处理发票...")
    for invoice in invoices:
        invoice_id = invoice["_id"]
        current_project = invoice.get("project_name", "")

        if current_project and current_project not in FIXED_PROJECTS and current_project != '其他':
            # 不在固定列表中，更新为"其他"
            await db.invoices.update_one(
                {"_id": invoice_id},
                {"$set": {"project_name": "其他"}}
            )
            updated_count += 1
            print(f"✓ 更新发票 {invoice_id}: {current_project} -> 其他")
        else:
            unchanged_count += 1
            if current_project:
                print(f"- 保持发票 {invoice_id}: {current_project}")

    print("\n" + "=" * 60)
    print("更新完成")
    print("=" * 60)
    print(f"总发票数: {total_count}")
    print(f"更新为'其他': {updated_count}")
    print(f"保持不变: {unchanged_count}")
    print("=" * 60)

    # 统计更新后的项目分布
    pipeline = [
        {"$match": {"project_name": {"$ne": None, "$ne": ""}}},
        {"$group": {"_id": "$project_name", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]

    project_stats = await db.invoices.aggregate(pipeline).to_list(length=None)

    print("\n更新后的项目分布:")
    print("-" * 60)
    for stat in project_stats:
        print(f"  {stat['_id']}: {stat['count']} 张发票")

    # 关闭数据库连接
    client.close()

if __name__ == "__main__":
    asyncio.run(update_project_names())
