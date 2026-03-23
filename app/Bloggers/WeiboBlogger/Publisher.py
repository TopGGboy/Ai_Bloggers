import os
from typing import Dict, Any, Optional

from playwright.async_api import Page, BrowserContext
from app.Bloggers.BasePublisher import BasePublisher
from app.tools.LoggingConfig import LoggingConfig
from app.core.config_manager import config


class WeiboPublisher(BasePublisher):
    """微博内容发布器 - 专注于内容生成和发布"""

    def __init__(self, context: BrowserContext, md_path: str):
        """
        初始化发布器

        Args:
            context: Playwright BrowserContext 实例
            md_path: Markdown 文件保存路径
        """
        super().__init__(context, md_path)

        # 组件
        self.Weibo_Login = None
        self.Weibo_SendEssay = None
        self.Weibo_WriteText = None

    async def init(self):
        """初始化发布器（不创建新 page，使用已有的 page）"""
        try:
            if not self.page:
                self.log.error("页面未初始化")
                raise ValueError("page 必须在使用前初始化")

            # 初始化组件
            from app.Bloggers.WeiboBlogger.module.SendEssay import AsyncSendEssay
            from app.Bloggers.WeiboBlogger.module.WriteText import WriteWeiboText

            self.Weibo_SendEssay = AsyncSendEssay(page=self.page)
            self.Weibo_WriteText = WriteWeiboText(model_name="deepseek-chat")

            self.log.info("微博发布器初始化成功（共用 page）")

        except Exception as e:
            self.log.error(f"知乎发布器初始化失败：{e}", exc_info=True)
            raise

    async def generate_and_publish(self, hot_title: dict) -> bool:
        """
        根据热榜信息生成内容并发布
        """
        try:
            # 初始化 GetHot 组件（临时使用)
            from app.Bloggers.WeiboBlogger.module.GetHot import AsyncWeiboGetHot
            weibo_get_hot = AsyncWeiboGetHot(page=self.page)

            # 获取热榜内容
            self.log.info(f"获取热榜内容：{hot_title['title']}")
            hot_text_content = await weibo_get_hot.get_hot_content_list(hot_title['href'])

            # AI生成文案
            self.log.info("✍️ 正在生成文案...")
            hot_text, _ = await self.Weibo_WriteText.write_hot_text_async(
                hot_title=hot_title['title'],
                hot_text_content=hot_text_content['content'],
                question_head=hot_text_content['question_head']
            )

            # 保存为json文件
            pass

        except Exception as e:
            self.log.error(f"生成并发布失败：{e}", exc_info=True)
            return False
