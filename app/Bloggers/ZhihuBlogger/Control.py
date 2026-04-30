import asyncio
from typing import Dict, Any, Optional, List
from enum import Enum

from playwright.async_api import Page, BrowserContext
from app.Bloggers.ZhihuBlogger.enums import ZhihuPublishType
from app.Bloggers.enums import PlatformMode
from app.Bloggers.BasePlatform import BasePlatform


class ZhihuAsyncControl(BasePlatform):
    """
    知乎平台控制器 - 统一管理监控和发布

    核心特性:
    1. 三种运行模式：只监控、只发布、监控并发布
    2. 多发布类型支持：回答、文章（可扩展）
    3. 懒加载：按需初始化组件和页面
    4. 智能登录：全局只登录一次
    5. 独立页面：监控和发布页面隔离
    6. 优雅关闭：自动等待后台任务

    使用示例:
        # 只监控
        control = ZhihuAsyncControl(context, mode=PlatformMode.MONITOR_ONLY)
        await control.run()

        # 发布回答
        control = ZhihuAsyncControl(context, mode=PlatformMode.PUBLISH_ONLY,
                                   publish_type=ZhihuPublishType.ANSWER)
        await control.run()

        # 监控并自动发布
        control = ZhihuAsyncControl(context, mode=PlatformMode.MONITOR_AND_PUBLISH,
                                   publish_type=ZhihuPublishType.ANSWER)
        await control.run()
    """

    def __init__(self, context: BrowserContext, mode: str = None,
                 user_data_dir: str = None,
                 publish_type: ZhihuPublishType = ZhihuPublishType.ANSWER):
        """
        初始化控制器

        :param context: 浏览器上下文
        :param mode: 运行模式
        :param user_data_dir: 用户数据目录
        :param publish_type: 发布类型
        """
        super().__init__(
            platform_name="zhihu",
            context=context,
            mode=mode,
            user_data_dir=user_data_dir,
            publish_type=publish_type
        )

    async def _init_monitor(self):
        """初始化监控器"""
        from app.Bloggers.ZhihuBlogger.Monitor import ZhihuMonitor

        self.monitor = ZhihuMonitor(context=self.context)
        await self._ensure_monitor_page()
        self.log.info("✅ 监控器已初始化")

    async def _init_publisher(self):
        """初始化发布器"""
        from app.Bloggers.ZhihuBlogger.Publisher import ZhihuPublisher

        self.publisher = ZhihuPublisher(
            context=self.context,
            publish_type=self.publish_type
        )
        await self._ensure_publish_page()
        self.log.info(f"✅ 发布器已初始化（类型：{self.publish_type.value}）")

    async def _init_writer(self):
        """初始化写作器"""
        from app.Bloggers.ZhihuBlogger.Wirter import ZhihuWriter

        self.writer = ZhihuWriter()
        self._writer_initialized = True
        self.log.info("✅ 写作器已初始化")

    async def _ensure_logged_in(self):
        """确保已登录（全局只登录一次）"""
        if self._is_logged_in:
            return

        self.log.info("⏳ 正在登录知乎...")
        temp_page = await self.context.new_page()

        try:
            from app.Bloggers.ZhihuBlogger.actions.Login import AsyncZhihuLogin
            login = AsyncZhihuLogin(page=temp_page, user_data_dir=self.user_data_dir)
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

            from app.Bloggers.ZhihuBlogger.scraping.GetHot import AsyncZhihuGetHot
            from app.Bloggers.ZhihuBlogger.content.WriteText import WriteZhihuText

            get_hot = AsyncZhihuGetHot(page=self.publish_page)
            write_text = WriteZhihuText()

            # 2. 生成内容（使用 Writer）
            self.log.info(f"✍️ 正在生成内容...")
            json_data = await self.writer.write(
                hot_title=hot_title,
                get_hot_instance=get_hot,
                write_text_instance=write_text
            )

            # 3. 发布内容（使用 Publisher 的统一接口）
            self.log.info(f"📤 正在发布...")
            data = {
                "href": hot_title.get("href", None),
                "json_data": json_data
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
