"""定时任务服务：定期轮询邮箱"""
import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime

from ..core.database import Database
from .email_service import EmailService

logger = logging.getLogger(__name__)


class SchedulerService:
    """定时任务服务"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.email_service = None

    async def start(self):
        """启动定时任务"""
        logger.info("启动定时任务服务")

        # 初始化邮件服务
        db = Database.get_db()
        self.email_service = EmailService(db)

        # 添加邮箱轮询任务（每 5 分钟）
        self.scheduler.add_job(
            self.poll_emails,
            trigger=IntervalTrigger(minutes=5),
            id='poll_emails',
            name='邮箱轮询任务',
            replace_existing=True
        )

        # 启动调度器
        self.scheduler.start()
        logger.info("定时任务服务已启动")

        # 在后台立即执行一次（不阻塞启动）
        asyncio.create_task(self.poll_emails())

    async def stop(self):
        """停止定时任务"""
        logger.info("停止定时任务服务")
        self.scheduler.shutdown()

    async def poll_emails(self):
        """邮箱轮询任务"""
        try:
            logger.info(f"[{datetime.now()}] 开始邮箱轮询任务")
            result = await self.email_service.process_all_users()
            logger.info(f"邮箱轮询完成: {result}")
        except Exception as e:
            logger.error(f"邮箱轮询任务失败: {e}", exc_info=True)


# 全局调度器实例
scheduler_service = SchedulerService()
