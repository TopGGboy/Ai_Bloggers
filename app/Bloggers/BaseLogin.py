from abc import ABC, abstractmethod
from app.core.config_manager import config
from app.tools.LoggingConfig import LoggingConfig
from app.tools.ElementWaiter import AsyncElementWaiter
from playwright.async_api import Page, Locator, TimeoutError as PlaywrightTimeoutError


class BaseLogin(ABC):
    """
    抽象登录类 - 定义所有平台的统一登录类
    """

    def __init__(self, platform_name: str, page: Page, user_data_dir: str = None):
        """初始化抽象登录类"""
        self.user_data_dir = user_data_dir
        self.page = page
        self.waiter = AsyncElementWaiter(page=self.page)
        self.platform_name = self.__class__.__name__
        self.log = LoggingConfig(log_file_path=config.logfile_path, log_level=config.log_level).get_logger(
            f"{self.platform_name}.Login")

        # 配置项
        self.url = config.platforms[platform_name]["urls"].get("login")
        self.login_timeout = config.platforms[platform_name].get("login_timeout", 60000)
        self.login_type = config.platforms[platform_name]["login_type"]
        self.username = config.platforms[platform_name]["user_name"]
        self.password = config.platforms[platform_name]["password"]

    @abstractmethod
    async def login(self):
        """启动登录流程"""
        pass

    @abstractmethod
    async def _login_by_username_and_password(self, username: str = None, password: str = None):
        """账号密码登录"""
        pass

    @abstractmethod
    async def _login_by_qrcode(self):
        """扫码登录"""
        pass
