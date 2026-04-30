import asyncio
import json
import os
from abc import ABC, abstractmethod
from playwright.async_api import BrowserContext, Page
from typing import Dict, Any, Optional, List, Callable

from app.tools.LoggingConfig import LoggingConfig
from app.core.config_manager import config


class BasePublisher(ABC):
    """
    内容发布器基类 - 定义所有发布器的统一接口
    """

    def __init__(self, platform_name: str, context: BrowserContext):
        """
        初始化发布器

        :param context: Playwright 的浏览器上下文，用于创建新页面
        """
        self.context = context
        self.page: Optional[Page] = None

        # 日志
        self.log = LoggingConfig(log_file_path=config.logfile_path, log_level=config.log_level).get_logger(
            self.__class__.__name__)
        # 配置项
        self.model_name = config.platforms[platform_name]["model"].get("name", "deepseek-chat")
        self.temp_path = config.temp_path

        # 重试配置
        self.retry_config = {
            "login": 3,
            "publish": 2
        }

    async def publish_essay(self, data: Dict[str, Any], Send_Action_class: Any) -> bool:
        """
        发布文章到知乎

        :param data: 内容字典，包含 title, content, images 等
        :param Send_Action_class: 发送操作类，用于发送发布请求
        :return: 发布是否成功
        """
        try:
            if not self.page:
                self.log.error("页面未初始化")
                return False

            await Send_Action_class.send_essay(data)
            self.log.info("发布回答成功")
            return True
        except Exception as e:
            self.log.error(f"发布回答失败：{e}", exc_info=True)
            return False
