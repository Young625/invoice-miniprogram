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
        self._polling_lock = asyncio.Lock()  # 添加锁防止并发轮询

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
        # 检查是否有轮询正在执行
        if self._polling_lock.locked():
            logger.warning("上一次轮询尚未完成，跳过本次执行")
            return

        async with self._polling_lock:
            try:
                start_time = datetime.now()
                logger.info(f"[{start_time}] 开始邮箱轮询任务")

                result = await self.email_service.process_all_users()

                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                logger.info(f"邮箱轮询完成: {result}, 耗时: {duration:.2f}秒")

                # 如果处理时间超过4分钟，发出警告
                if duration > 240:
                    logger.warning(f"⚠️ 轮询耗时过长: {duration:.2f}秒，建议优化或增加轮询间隔")

            except Exception as e:
                logger.error(f"邮箱轮询任务失败: {e}", exc_info=True)


# 全局调度器实例
scheduler_service = SchedulerService()
