from abc import ABC, abstractmethod
from app.core.config_manager import config
from app.tools.LoggingConfig import LoggingConfig
from playwright.async_api import Page, Locator, TimeoutError as PlaywrightTimeoutError


class BaseSendEssay(ABC):
    """
    抽象发文类 - 定义所有平台的统一发文类
    """

    def __init__(self, page: Page):
        """初始化抽象发文类"""
        self.page = page
        self.log = LoggingConfig(log_file_path=config.logfile_path, log_level=config.log_level).get_logger(
            f"{self.__class__.__name__}.SendEssay")

    @abstractmethod
    async def send_essay(self, file_path: str, href: str):
        """发送文章"""
        pass
