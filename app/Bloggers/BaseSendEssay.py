from abc import ABC, abstractmethod
from app.core.config_manager import config
from app.tools.LoggingConfig import LoggingConfig
from app.tools.ElementWaiter import AsyncElementWaiter
from playwright.async_api import Page, Locator, TimeoutError as PlaywrightTimeoutError


class BaseSendEssay(ABC):
    """
    抽象发文类 - 定义所有平台的统一发文类
    """

    def __init__(self, platform_name: str, page: Page):
        """初始化抽象发文类"""
        self.page = page
        self.waiter = AsyncElementWaiter(page=self.page)
        self.log = LoggingConfig(log_file_path=config.logfile_path, log_level=config.log_level).get_logger(
            f"{self.__class__.__name__}.SendEssay")

        self.url = config.platforms[platform_name]["urls"].get("hot_list")
        self.element_timeout = config.platforms[platform_name]["element_timeout"]

    @abstractmethod
    async def send_essay(self, file_path: str, href: str):
        """发送文章"""
        pass
