import json
import os
import asyncio
from typing import Optional, List, Callable

from playwright.async_api import Page, BrowserContext
from app.core.config_manager import config

from app.Bloggers.BaseMonitor import BaseMonitor


class WeiboMonitor(BaseMonitor):
    """微博监控器 - 专注于监微博变化"""

    def __init__(self, context: BrowserContext):
        """
        初始化监控器

        :param context: Playwright BrowserContext 实例
        """
        super().__init__(platform_name="weibo", context=context)
        self.Weibo_GetHot = None

    async def init(self) -> None:
        """初始化监控器（不创建新 page，使用已有的 page）"""
        try:
            if not self.page:
                self.log.error("页面未初始化")
                raise ValueError("page 必须在使用前初始化")

            # 初始化获取热榜组件
            from app.Bloggers.WeiboBlogger.module.GetHot import AsyncWeiboGetHot
            self.Weibo_GetHot = AsyncWeiboGetHot(page=self.page)

            self.log.info("微博监控器初始化成功")

        except Exception as e:
            self.log.error(f"微博监控器初始化失败：{e}", exc_info=True)
            raise
