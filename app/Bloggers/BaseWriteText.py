from abc import ABC, abstractmethod
from app.core.config_manager import config
from app.tools.LoggingConfig import LoggingConfig
from playwright.async_api import Page, Locator, TimeoutError as PlaywrightTimeoutError


class BaseWriteText(ABC):
    """
    抽象发文类 - 定义所有平台的统一写文类
    """

    def __init__(self):
        """初始化抽象创作类"""
        self.log = LoggingConfig(log_file_path=config.logfile_path, log_level=config.log_level).get_logger(
            f"{self.__class__.__name__}.WriteText")

    async def write_hot_text_async(self, hot_title: str, hot_content: list, question_head: str) -> tuple[str, list]:
        """
        异步版本：根据热点话题创作知乎文章

        Args:
            hot_title (str): 热点话题标题
            hot_content (list): 热点话题详细内容
            question_head (str): 热点话题问题简介

        Returns:
            tuple: (生成的文章内容，消息历史记录)
        """
        pass
