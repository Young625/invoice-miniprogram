"""日志配置模块 - 按日期轮转并压缩"""
import logging
import os
import gzip
import shutil
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
import zipfile


class CompressedTimedRotatingFileHandler(TimedRotatingFileHandler):
    """
    自定义日志处理器:
    - 按天轮转
    - 自动压缩为 ZIP 格式
    - 按月份组织目录结构
    """

    def __init__(self, base_dir, filename_prefix, when='midnight', interval=1,
                 backupCount=0, encoding='utf-8', delay=False, utc=False):
        """
        初始化处理器

        Args:
            base_dir: 日志基础目录 (例如: logs)
            filename_prefix: 文件名前缀 (例如: application, application-error)
            when: 轮转时间单位 (默认: midnight - 每天午夜)
            interval: 轮转间隔
            backupCount: 保留的备份数量 (0表示不限制)
            encoding: 文件编码
        """
        self.base_dir = base_dir
        self.filename_prefix = filename_prefix

        # 创建基础目录
        os.makedirs(base_dir, exist_ok=True)

        # 获取当前日志文件路径
        current_log_file = self._get_current_log_path()

        # 初始化父类
        super().__init__(
            filename=current_log_file,
            when=when,
            interval=interval,
            backupCount=backupCount,
            encoding=encoding,
            delay=delay,
            utc=utc
        )

    def _get_current_log_path(self):
        """获取当前日志文件路径"""
        today = datetime.now()
        year_month = today.strftime('%Y-%m')
        month_dir = os.path.join(self.base_dir, year_month)
        os.makedirs(month_dir, exist_ok=True)

        # 当前日志文件名 (不带日期后缀)
        return os.path.join(month_dir, f'{self.filename_prefix}.log')

    def doRollover(self):
        """
        执行日志轮转
        1. 关闭当前文件
        2. 重命名为带日期的文件
        3. 压缩为 ZIP
        4. 删除原始文件
        5. 打开新文件
        """
        import time

        if self.stream:
            self.stream.close()
            self.stream = None

        # 获取昨天的日期（轮转在午夜触发，此时 now() 已是新的一天，减1秒得到昨天）
        from datetime import timedelta
        yesterday = datetime.now() - timedelta(seconds=1)
        date_str = yesterday.strftime('%Y-%m-%d')
        year_month = yesterday.strftime('%Y-%m')

        # 确保月份目录存在
        month_dir = os.path.join(self.base_dir, year_month)
        os.makedirs(month_dir, exist_ok=True)

        # 源文件路径 (当前日志文件)
        source_file = self.baseFilename

        # 目标文件路径 (带日期的日志文件)
        target_file = os.path.join(month_dir, f'{self.filename_prefix}-{date_str}.0.log')

        # ★ 关键修复：必须在任何 logging 调用之前更新 rolloverAt 和 baseFilename，
        #   否则 logging.info() 会再次触发 shouldRollover() → doRollover() 连锁反应
        self.rolloverAt = self.computeRollover(int(time.time()))
        self.baseFilename = self._get_current_log_path()

        # 如果源文件存在且有内容,进行轮转
        if os.path.exists(source_file) and os.path.getsize(source_file) > 0:
            # 重命名文件
            if os.path.exists(target_file):
                os.remove(target_file)
            os.rename(source_file, target_file)

            # 压缩为 ZIP
            zip_file = target_file + '.zip'
            try:
                with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zf:
                    zf.write(target_file, os.path.basename(target_file))

                # 删除原始日志文件
                os.remove(target_file)

                logging.info(f'日志已轮转并压缩: {zip_file}')
            except Exception as e:
                logging.error(f'压缩日志文件失败: {e}')

        # 打开新的日志文件
        if not self.delay:
            self.stream = self._open()

    def _open(self):
        """打开日志文件"""
        # 确保目录存在
        log_dir = os.path.dirname(self.baseFilename)
        os.makedirs(log_dir, exist_ok=True)

        return open(self.baseFilename, self.mode, encoding=self.encoding)


def setup_logging(base_dir='logs', log_level=logging.INFO):
    """
    配置日志系统

    Args:
        base_dir: 日志基础目录
        log_level: 日志级别

    Returns:
        配置好的 logger
    """
    # 创建日志目录
    os.makedirs(base_dir, exist_ok=True)

    # 日志格式
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    formatter = logging.Formatter(log_format)

    # 获取根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 清除现有处理器
    root_logger.handlers.clear()

    # 1. 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 2. 应用日志处理器 (所有级别)
    app_handler = CompressedTimedRotatingFileHandler(
        base_dir=base_dir,
        filename_prefix='application',
        when='midnight',
        interval=1,
        backupCount=0,  # 不限制备份数量
        encoding='utf-8'
    )
    app_handler.setLevel(logging.DEBUG)
    app_handler.setFormatter(formatter)
    root_logger.addHandler(app_handler)

    # 3. 错误日志处理器 (只记录 ERROR 及以上)
    error_handler = CompressedTimedRotatingFileHandler(
        base_dir=base_dir,
        filename_prefix='application-error',
        when='midnight',
        interval=1,
        backupCount=0,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)

    return root_logger
