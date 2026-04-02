import asyncio
import json
import os
from abc import ABC, abstractmethod
from playwright.async_api import BrowserContext, Page
from typing import Dict, Any, Optional, List, Callable

from app.tools.LoggingConfig import LoggingConfig
from app.core.config_manager import config
from app.tools.Str2Md import Str2Md


class BasePublisher(ABC):
    """
    内容发布器基类 - 定义所有发布器的统一接口
    """

    def __init__(self, platform_name: str, context: BrowserContext, md_path: str):
        """
        初始化发布器

        :param context: Playwright 的浏览器上下文，用于创建新页面
        """
        self.context = context
        self.page: Optional[Page] = None
        self.md_path: Optional[str] = None

        self.str_2_md = Str2Md()

        # 日志
        self.log = LoggingConfig(log_file_path=config.logfile_path, log_level=config.log_level).get_logger(
            self.__class__.__name__)
        # 配置项
        self.model_name = config.platforms[platform_name]["model"].get("name", "deepseek-chat")

        # 重试配置
        self.retry_config = {
            "login": 3,
            "publish": 2
        }

    async def init(self):
        """初始化发布器(不创建新 page，使用已有的 page)"""
        pass

    async def publish_answer(self, content: Dict[str, Any], url: str = None) -> bool:
        """
        发布回答到知乎

        :param url: 待发布的内容链接
        :param content: 内容字典，包含 title, content, images 等
        :return: 发布是否成功
        """
        pass

    async def generate_and_publish(self, hot_title: dict) -> bool:
        """
        根据热榜信息生成内容并发布

        :param hot_title: 热榜标题信息字典，包含 title, href 等
        :return: 是否成功
        """
        pass

    def _sanitize_filename(self, title: str) -> str:
        """清理标题中的特殊字符，使其适合作为文件名"""
        invalid_chars = r'<>"|*?/\\:'
        sanitized = title
        for char in invalid_chars:
            sanitized = sanitized.replace(char, '_')

        sanitized = ' '.join(sanitized.split())

        max_length = 200
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]

        return sanitized
