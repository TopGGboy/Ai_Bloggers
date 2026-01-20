import logging
from pathlib import Path
from typing import Optional
import sys


class LoggingConfig:
    """
    日志配置类，用于统一管理文件和控制台日志输出。
    支持彩色日志输出（仅控制台），并提供标准日志接口。
    """

    # 类变量用于实现单例模式
    _instance = None
    _initialized = False

    # 默认日志文件名和格式
    DEFAULT_LOG_FILENAME = "app.log"
    DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
            self,
            log_file_path: Optional[Path] = None,
            log_filename: str = DEFAULT_LOG_FILENAME,
            log_level: int = logging.INFO,
    ):
        """
        初始化日志系统

        :param log_file_path: 日志文件存储目录路径，默认为当前工作目录
        :param log_filename: 日志文件名，默认为 app.log
        :param log_level: 日志级别，默认为 INFO
        """
        # 防止重复初始化
        if hasattr(self, '_initialized') and self._initialized:
            return

        self._initialized = True

        # 设置日志路径和文件
        self.log_file_path = log_file_path or Path.cwd()
        self.log_filepath = self._build_log_filepath(log_filename)
        self.log_level = log_level

        # 获取根日志记录器并设置全局日志级别
        self.logger = logging.getLogger()

        # 检查是否已经有配置过的处理器
        if self.logger.handlers:
            # 如果已经有处理器，则不重复添加
            return

        self.logger.setLevel(self.log_level)

        # 创建统一的日志格式器
        formatter = logging.Formatter(self.DEFAULT_LOG_FORMAT)

        # 配置日志处理器
        self._setup_file_handler(formatter)
        self._setup_console_handler()

    class ColoredFormatter(logging.Formatter):
        """
        带颜色的日志格式器，使用 ANSI 转义码在终端中显示不同颜色的日志级别
        """

        COLORS = {
            'DEBUG': '\033[94m',  # 蓝色
            'INFO': '\033[92m',  # 绿色
            'WARNING': '\033[93m',  # 黄色
            'ERROR': '\033[91m',  # 红色
            'CRITICAL': '\033[95m',  # 紫色
        }
        RESET = '\033[0m'  # 重置颜色

        def format(self, record):
            """
            格式化日志记录，并添加颜色前缀

            :param record: 日志记录对象
            :return: 带颜色的日志字符串
            """
            color = self.COLORS.get(record.levelname, self.RESET)
            message = super().format(record)
            return f"{color}{message}{self.RESET}"

    def _build_log_filepath(self, filename: str) -> Path:
        """
        构建完整的日志文件路径

        :param filename: 日志文件名
        :return: 解析后的完整路径对象
        """
        return (self.log_file_path / filename).resolve()

    def _setup_file_handler(self, formatter: logging.Formatter):
        """
        配置文件日志处理器，将日志写入到指定文件中

        :param formatter: 日志格式器
        """
        file_handler = logging.FileHandler(str(self.log_filepath))
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    def _setup_console_handler(self):
        """
        配置控制台日志处理器，支持彩色输出
        """
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(self.ColoredFormatter(self.DEFAULT_LOG_FORMAT))
        console_handler.setLevel(self.log_level)
        self.logger.addHandler(console_handler)

    def get_logger(self) -> logging.Logger:
        """
        返回配置好的日志记录器实例

        :return: logging.Logger 对象
        """
        return self.logger

    def __call__(self) -> logging.Logger:
        """
        支持将该实例作为函数调用，返回日志记录器

        :return: logging.Logger 对象
        """
        return self.get_logger()
