import os
from typing import Dict, Any, Optional
import json
from pathlib import Path

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

        # JSON 文件保存路径
        self.json_path = "./weibo_content.json"

    async def init(self):
        """初始化发布器（不创建新 page，使用已有的 page）"""
        try:
            if not self.page:
                self.log.error("页面未初始化")
                raise ValueError("page 必须在使用前初始化")

            # 初始化组件
            from app.Bloggers.WeiboBlogger.module.SendEssay import AsyncWeiboSendEssay
            from app.Bloggers.WeiboBlogger.module.WriteText import WriteWeiboText

            self.Weibo_SendEssay = AsyncWeiboSendEssay(page=self.page)
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
            self.log.info("💾 正在保存生成的内容...")
            self._append_to_json(hot_text)

            # 在主页面执行发布操作
            self.log.info("📤 正在发布文章...")
            await self.Weibo_SendEssay.send_essay(content=hot_text, href=hot_title['href'])

            self.log.info(f"✅ 推文发布成功：{hot_title['title']}")
            return True
        except Exception as e:
            self.log.error(f"生成并发布失败：{e}", exc_info=True)
            return False

    def _append_to_json(self, data: dict) -> None:
        """
        将数据追加到 JSON 文件中

        :param data: 要保存的字典数据
        """
        # 如果文件不存在，创建空列表
        if not self.json_path.exists():
            with open(self.json_path, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)

        # 读取现有内容
        with open(self.json_path, 'r', encoding='utf-8') as f:
            content_list = json.load(f)

        # 追加新数据
        content_list.append(data)

        # 写回文件
        with open(self.json_path, 'w', encoding='utf-8') as f:
            json.dump(content_list, f, ensure_ascii=False, indent=2)

        self.log.info(f"内容已保存到：{self.json_path}")
