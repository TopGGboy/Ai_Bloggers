import asyncio
from typing import Dict, Any, Optional, List
from enum import Enum

from playwright.async_api import Page, BrowserContext
from app.Bloggers.WeiboBlogger.PublishTypeEnums import WeiboPublishType
from app.Bloggers.PlatformEnums import PlatformMode
from app.Bloggers.BasePlatform import BasePlatform


class WeiboAsyncControl(BasePlatform):
    """
    微博异步控制类
    """

    def __init__(self, context: BrowserContext, mode: str = None,
                 user_data_dir: str = None,
                 publish_type: WeiboPublishType = WeiboPublishType.ESSAY):
        """
        初始化控制器

        :param context: Playwright BrowserContext 实例
        :param mode: 运行模式
        :param user_data_dir: 用户数据目录（如 "user_data")
        :param publish_type: 发布类型（如 WeiboPublishType.ESSAY）
        """
        super().__init__(
            platform_name="weibo",
            context=context,
            mode=mode,
            user_data_dir=user_data_dir,
            publish_type=publish_type
        )

    async def _init_monitor(self) -> None:
        """初始化监控器"""
        from app.Bloggers.WeiboBlogger.Monitor import WeiboMonitor

        self.monitor = WeiboMonitor(context=self.context)
        await self._ensure_monitor_page()
        self.log.info("✅ 监控器已初始化")

    async def _init_publisher(self) -> None:
        """初始化发布器"""
        from app.Bloggers.WeiboBlogger.Publisher import WeiboPublisher

        self.publisher = WeiboPublisher(
            context=self.context,
            publish_type=self.publish_type
        )
        await self._ensure_publish_page()
        self.log.info(f"✅ 发布器已初始化（类型：{self.publish_type}）")

    async def _init_writer(self) -> None:
        """初始化写作器"""
        from app.Bloggers.WeiboBlogger.Wirter import WeiboWriter

        self.writer = WeiboWriter()
        self._writer_initialized = True
        self.log.info("✅ 写作器已初始化")

    async def _ensure_logged_in(self) -> None:
        """确保已经登录"""
        if self._is_logged_in:
            return

        self.log.info("⏳ 正在登录微博...")
        temp_page = await self.context.new_page()

        try:
            from app.Bloggers.WeiboBlogger.actions.Login import AsyncWeiboLogin
            login = AsyncWeiboLogin(page=temp_page, user_data_dir=self.user_data_dir)
            await login.login()
            self._is_logged_in = True
            self.log.info("✅ 登录成功")
        finally:
            await temp_page.close()

    async def _process_hot_title_async(self, hot_title: dict) -> bool:
        """处理热榜变化的异步任务 - 先生成后发布"""
        try:
            await self._ensure_publish_page()

            self.log.info(f"📝 开始生成并发布：{hot_title['title']}")

            # 1. 初始化依赖组件（如果未初始化）
            if not self._writer_initialized:
                await self._init_writer()

            from app.Bloggers.WeiboBlogger.scraping.GetHot import AsyncWeiboGetHot
            from app.Bloggers.WeiboBlogger.content.WriteText import WriteWeiboText

            get_hot = AsyncWeiboGetHot(page=self.publish_page)
            write_text = WriteWeiboText(model_name=self.publisher.model_name)

            # 2. 生成内容（使用 Writer）
            self.log.info(f"✍️ 正在生成内容...")
            md_path, json_data = await self.writer.write(
                hot_title=hot_title,
                Get_Hot_Class=get_hot,
                Write_Text_Class=write_text
            )

            if not md_path:
                self.log.error(f"❌ 内容生成失败：{hot_title['title']}")
                return False

            # 3. 发布内容（使用 Publisher 的统一接口）
            self.log.info(f"📤 正在发布...")
            data = {
                "title": json_data.get("title"),
                "content": json_data.get("content"),
                "image_path": json_data.get("image_path"),
                "summary": json_data.get("summary")
            }
            result = await self.publisher.publish(data)

            if result:
                self.log.info(f"✅ {self.publish_type.value} 发布成功：{hot_title['title']}")
            else:
                self.log.error(f"❌ {self.publish_type.value} 发布失败：{hot_title['title']}")

            return result

        except Exception as e:
            self.log.error(f"❌ 处理热榜变化失败：{e}", exc_info=True)
            return False
