import os
from typing import Dict, Any

from playwright.async_api import BrowserContext
from app.Bloggers.BasePublisher import BasePublisher
from app.core.config_manager import config


class ZhihuPublisher(BasePublisher):
    """知乎内容发布器 - 专注于内容生成和发布"""

    def __init__(self, context: BrowserContext, md_path: str):
        """
        初始化发布器

        Args:
            context: Playwright BrowserContext 实例
            md_path: Markdown 文件保存路径
        """
        super().__init__(platform_name="zhihu", context=context, md_path=md_path)

        # 组件
        self.Zhihu_Login = None
        self.Zhihu_SendAnswer = None
        self.Zhihu_WriteText = None

    async def init(self) -> None:
        """初始化发布器（不创建新 page，使用已有的 page）"""
        try:
            if not self.page:
                self.log.error("页面未初始化")
                raise ValueError("page 必须在使用前初始化")

            # 初始化组件
            from app.Bloggers.ZhihuBlogger.module.SendAnswer import AsyncZhihuSendAnswer
            from app.Bloggers.ZhihuBlogger.module.WriteText import WriteZhihuText

            self.Zhihu_SendAnswer = AsyncZhihuSendAnswer(page=self.page)
            self.Zhihu_WriteText = WriteZhihuText(model_name=self.model_name)

            self.log.info("知乎发布器初始化成功（共用 page）")

        except Exception as e:
            self.log.error(f"知乎发布器初始化失败：{e}", exc_info=True)
            raise

    async def publish_answer(self, content: Dict[str, Any], url: str = None) -> bool:
        """
        发布回答到知乎

        Args:
            url: 目标问题的链接
            content: 内容字典，包含 title, content, images 等

        Returns:
            bool: 发布是否成功
        """
        try:
            if not self.page:
                self.log.error("页面未初始化")
                return False

            # 从 content 中提取数据
            title = content.get('title', '')
            text_content = content.get('content', '')

            # 保存为 Markdown 文件
            sanitized_title = self._sanitize_filename(title)
            file_name = os.path.join(self.md_path, f"{sanitized_title}.md")
            self.str_2_md.save_2_md(text_content, file_name=file_name)

            await self.Zhihu_SendAnswer.login()

            self.log.info(f"内容发布成功：{title}")
            return True

        except Exception as e:
            self.log.error(f"发布内容失败：{e}", exc_info=True)
            return False

    async def generate_and_publish(self, hot_title: dict) -> bool:
        """
        根据热榜信息生成内容并发布

        Args:
            hot_title: 热榜标题信息字典，包含 title, href 等

        Returns:
            bool: 是否成功
        """
        try:
            # 初始化 GetHot 组件（临时使用）
            from app.Bloggers.ZhihuBlogger.module.GetHot import AsyncZhihuGetHot
            zhihu_get_hot = AsyncZhihuGetHot(page=self.page, logging=True)

            # 获取热榜内容
            self.log.info(f"📖 正在获取内容：{hot_title['title']}")
            hot_text_content = await zhihu_get_hot.get_hot_content_list(hot_title['href'])

            # AI 生成文案
            self.log.info("✍️ 正在生成文案...")
            hot_text, _ = await self.Zhihu_WriteText.write_hot_text_async(
                hot_title['title'],
                hot_text_content['content'],
                hot_text_content['question_head']
            )

            # 使用标题生成安全的文件名
            sanitized_title = self._sanitize_filename(hot_title['title'])
            file_path = os.path.join(self.md_path, f"{sanitized_title}.md")

            # 保存 Markdown 文件
            self.str_2_md.save_2_md(hot_text, file_name=file_path)
            self.log.info(f"文章已保存至：{file_path}")

            # 【关键】在主发布页面上执行发布操作
            self.log.info("📤 正在发布文章...")
            await self.Zhihu_SendAnswer.send_essay(href=hot_title['href'], file_path=file_path)

            self.log.info(f"✅ 文章发布成功：{hot_title['title']}")
            return True

        except Exception as e:
            self.log.error(f"生成并发布失败：{e}", exc_info=True)
            return False
