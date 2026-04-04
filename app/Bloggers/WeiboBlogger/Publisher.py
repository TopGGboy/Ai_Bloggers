import os
from typing import Dict, Any, Optional

from playwright.async_api import Page, BrowserContext
from app.Bloggers.BasePublisher import BasePublisher
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
        super().__init__(platform_name="weibo", context=context, md_path=md_path)

    async def init(self):
        """初始化发布器（不创建新 page，使用已有的 page）"""
        try:
            if not self.page:
                self.log.error("页面未初始化")
                raise ValueError("page 必须在使用前初始化")

            # 初始化组件
            from app.Bloggers.WeiboBlogger.module.SendEssay import AsyncWeiboSendEssay
            from app.Bloggers.WeiboBlogger.module.WriteText import WriteWeiboText
            from app.Bloggers.WeiboBlogger.module.GetHot import AsyncWeiboGetHot
            from app.Bloggers.WeiboBlogger.Wirter import WeiboWriter

            self.Weibo_SendEssay = AsyncWeiboSendEssay(page=self.page)
            self.Weibo_WriteText = WriteWeiboText(model_name=self.model_name)
            self.Weibo_GetHot = AsyncWeiboGetHot(page=self.page)
            self.Weibo_Writer = WeiboWriter()

            self.log.info("微博发布器初始化成功（共用 page）")

        except Exception as e:
            self.log.error(f"知乎发布器初始化失败：{e}", exc_info=True)
            raise

    async def generate_and_publish(self, hot_title: dict) -> bool:
        """
        根据热榜信息生成内容并发布
        """
        try:
            md_path, json_data = await self.Zhihu_Writer.write(hot_title=hot_title, Get_Hot_Class=self.Weibo_GetHot,
                                                               Write_Text_Class=self.Weibo_WriteText)

            # 在主页面执行发布操作
            self.log.info("📤 正在发布文章...")
            await self.Weibo_SendEssay.send_essay(content=json_data, href=hot_title['href'])

            self.log.info(f"✅ 推文发布成功：{hot_title['title']}")
            return True
        except Exception as e:
            self.log.error(f"生成并发布失败：{e}", exc_info=True)
            return False
