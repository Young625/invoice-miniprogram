"""FastAPI 应用入口"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.core.database import Database
from app.core.logging_config import setup_logging
from app.api import auth, invoice, user, reimbursement
from app.services.scheduler_service import scheduler_service

# 配置日志系统
# 按日期轮转,自动压缩为ZIP,按月份组织
setup_logging(base_dir='logs', log_level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    await Database.connect_db()
    print(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} 启动成功")

    # 启动定时任务
    await scheduler_service.start()
    print("⏰ 邮箱监控服务已启动（每 5 分钟检查一次）")

    yield

    # 关闭时
    await scheduler_service.stop()
    await Database.close_db()
    print("👋 应用已关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="发票管理系统 API - 自动监控邮箱，实时提取发票",
    lifespan=lifespan
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(invoice.router, prefix=settings.API_PREFIX)
app.include_router(user.router, prefix=settings.API_PREFIX)
app.include_router(reimbursement.router, prefix=settings.API_PREFIX)


@app.get("/")
async def root():
    """根路径"""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "features": [
            "自动邮箱监控（每 5 分钟）",
            "智能发票提取",
            "实时统计分析"
        ]
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
