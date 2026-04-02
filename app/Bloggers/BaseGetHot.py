from abc import ABC, abstractmethod
from app.core.config_manager import config
from app.tools.LoggingConfig import LoggingConfig
from playwright.async_api import Page, Locator, TimeoutError as PlaywrightTimeoutError


class BaseGetHot(ABC):
    """
    抽象获取热榜类 - 定义所有平台的统一获取热榜类
    """

    def __init__(self, platform_name: str, page: Page):
        """初始化抽象获取热榜类"""
        self.page = page
        self.waiter = AsyncElementWaiter(self.page)
        self.log = LoggingConfig(log_file_path=config.logfile_path, log_level=config.log_level).get_logger(
            f"{self.__class__.__name__}.GetHot")

        # 从配置文件中获取热榜 URL
        self.url = config.platforms[platform_name]["urls"].get("hot_list")

    @abstractmethod
    async def get_hot_title_list(self, begin, end):
        """获取指定范围内的热榜标题"""
        pass

    @abstractmethod
    async def get_hot_content_list(self, href):
        """获取热榜内容"""
        pass
