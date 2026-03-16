from abc import ABC, abstractmethod
from playwright.async_api import BrowserContext, Page
import logging
from typing import Dict, Any, Optional
import asyncio

from app.core.config_manager import config
from app.tools.LoggingConfig import LoggingConfig


class BasePlatform(ABC):
    """
    平台基类 - 定义所有平台的统一接口

    核心特性:
    1. 每个平台独占一个 BrowserContext（隔离 Cookie/指纹）
    2. 统一的初始化和发布接口
    3. 支持异步操作
    """

    def __init__(self, context: BrowserContext, md_path: str, mode: str = None, user_data_dir: str = None):
        """
        初始化平台

        Args:
            context: 独立的浏览器上下文（每个平台一个）
            md_path: Markdown 文件存储路径
        """
        self.user_data_dir = user_data_dir
        self.context = context
        self.page: Optional[Page] = None
        self.md_path = md_path
        self.platform_name = self.__class__.__name__
        self.log = LoggingConfig(log_file_path=config.logfile_path, log_level=config.log_level).get_logger(
            f"{self.platform_name}.Control")

    @abstractmethod
    async def run(self, check_interval: int = 600) -> None:
        """
        平台主运行方法 - 根据模式执行不同的逻辑

        :param check_interval: 监控循环间隔（秒），默认 600 秒
        :return:
        """
        pass

    @abstractmethod
    async def publish_content(self, content: Dict[str, Any], url: str = None) -> bool:
        """
        发布内容到平台

        Args:
            content: 内容字典，包含 title, content, images 等
            url: 目标话题链接

        Returns:
            bool: 发布是否成功
        """
        pass

    @abstractmethod
    async def run_monitor(self) -> None:
        """运行监控任务"""
        pass

    @abstractmethod
    async def get_hot_list(self, start_index: int, end_index: int) -> list:
        """
        获取热榜数据

        Args:
            start_index: 起始索引
            end_index: 结束索引

        Returns:
            list: 热榜数据列表
        """
        pass

    async def close(self) -> None:
        """关闭平台资源"""
        if self.page:
            await self.page.close()
        self.log.info(f"{self.platform_name} 资源已关闭")

    async def random_sleep(self, min_seconds: float = 1.0, max_seconds: float = 3.0) -> None:
        """随机延迟（模拟真人操作）"""
        import random
        delay = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(delay)
        self.log.debug(f"延迟 {delay:.2f}秒")
