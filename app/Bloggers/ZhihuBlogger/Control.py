import time
import json
import os
import asyncio
from enum import Enum, auto

from playwright.sync_api import Page
from playwright.async_api import BrowserContext
from typing import Dict, Any, Optional, List

from app.tools.LoggingConfig import LoggingConfig
from app.core.config_manager import config
from app.Bloggers.BasePlatform import BasePlatform


class ZhihuAsyncControl(BasePlatform):
    """
    异步版本的知乎平台控制器，整合了监控和发布功能。

    职责：
    - 管理知乎的登录状态（全局一次）
    - 初始化监控器（ZhihuMonitor）和发布器（ZhihuPublisher）
    - 提供发布内容、获取热榜、运行监控的接口
    - 处理热榜变化时的异步回调，确保不阻塞监控主循环
    - 优雅关闭并等待后台任务完成
    """

    def __init__(self, context: BrowserContext, md_path: str):
        """
        初始化知乎异步控制器。

        :param context: Playwright 的浏览器上下文，用于创建新页面
        :param md_path: Markdown 文件的路径，发布器需要用到的资源
        """
        super().__init__(context, md_path)

        # 追踪所有异步任务，用于在关闭时等待或取消
        self.background_tasks: set = set()

        # 监控器和发布器实例，懒加载初始化
        self.monitor = None
        self.publisher = None

        # 监控页面和发布页面，各自独立，避免互相干扰
        self.monitor_page: Optional[Page] = None
        self.publish_page: Optional[Page] = None

        # 状态配置
        self.url = "https://www.zhihu.com/hot"  # 热榜页面 URL
        self.user_input = ""  # 用户输入（暂未使用）
        self.start_index: Optional[int] = 1  # 监控起始索引（热榜第几位开始）
        self.end_index: Optional[int] = 1  # 监控结束索引
        self.hot_titles: Optional[List] = None  # 缓存的热榜标题列表
        self._is_logged_in = False  # 登录状态标记

        # 保存 markdown 文件的路径（从入参接收）
        self.md_path = md_path
        # 重试配置，提高健壮性（目前未在代码中显式使用，可后续扩展）
        self.retry_config = {
            "login": 3,
            "publish": 2,
            "get_hot": 2
        }

    async def init(self) -> None:
        """
        初始化平台：导入监控器和发布器模块，并创建实例。
        登录步骤将在需要时由 `_ensure_logged_in` 自动触发。
        """
        try:
            # 延迟导入，避免循环依赖
            from app.Bloggers.ZhihuBlogger.Monitor import ZhihuMonitor
            from app.Bloggers.ZhihuBlogger.Publisher import ZhihuPublisher

            # 初始化监控器（此时尚未关联页面，页面在 `_ensure_monitor_page` 中创建）
            self.monitor = ZhihuMonitor(context=self.context)

            # 初始化发布器
            self.publisher = ZhihuPublisher(context=self.context, md_path=self.md_path)

            # 设置监控器的变化回调，当热榜变化时自动调用 `_on_hot_title_change`
            self.monitor.on_change(self._on_hot_title_change)

            self.log.info("✅ 知乎平台初始化成功")

        except Exception as e:
            self.log.error(f"❌ 知乎平台初始化失败：{e}", exc_info=True)
            raise

    async def _ensure_logged_in(self):
        """
        确保已经登录知乎。
        如果 `_is_logged_in` 为 False，则执行登录流程。
        登录使用独立的临时页面，完成后关闭该页面。
        """
        if not self._is_logged_in:
            self.log.info("⏳ 正在登录知乎...")
            # 创建一个临时页面用于登录
            temp_page = await self.context.new_page()
            from app.Bloggers.ZhihuBlogger.Login import AsyncLogin
            login = AsyncLogin(page=temp_page)
            await login.run()
            await temp_page.close()  # 登录完成后关闭临时页面
            self._is_logged_in = True
            self.log.info("✅ 登录成功")

    async def _ensure_monitor_page(self) -> Page:
        """
        确保监控页面已创建并返回该页面。
        如果页面不存在或已关闭，则新建页面并执行登录（如果需要）。

        :return: 可用的监控页面对象
        """
        if self.monitor_page is None or self.monitor_page.is_closed():
            self.log.info("📄 创建监控页面...")
            self.monitor_page = await self.context.new_page()

            # 确保已登录（全局只需一次）
            await self._ensure_logged_in()

            # 将页面设置到监控器，并让监控器完成初始化（不需要再新建页面）
            self.monitor.page = self.monitor_page
            await self.monitor.init_without_new_page()
        return self.monitor_page

    async def _ensure_publish_page(self) -> Page:
        """
        确保发布页面已创建并返回该页面。
        如果页面不存在或已关闭，则新建页面并执行登录。

        :return: 可用的发布页面对象
        """
        if self.publish_page is None or self.publish_page.is_closed():
            self.log.info("📄 创建发布页面...")
            self.publish_page = await self.context.new_page()

            await self._ensure_logged_in()

            # 将页面设置到发布器，并让发布器完成初始化
            self.publisher.page = self.publish_page
            await self.publisher.init_without_new_page()
        return self.publish_page

    async def _on_hot_title_change(self, hot_title: dict):
        """
        当监控器检测到热榜变化时的回调函数。
        此回调会被监控器在检测到变化时调用，它负责异步启动内容生成和发布任务，
        并立即返回，避免阻塞监控循环。

        :param hot_title: 发生变化的热榜项字典，包含 'title', 'url' 等信息
        """
        try:
            self.log.info(f"🔔 回调函数被调用：{hot_title['title']}")

            # 创建异步任务来处理该热榜项，并追踪它
            task = asyncio.create_task(
                self._process_hot_title_async(hot_title)
            )
            self.background_tasks.add(task)

            # 任务完成后自动从集合中移除
            task.add_done_callback(lambda t: self.background_tasks.discard(t))

            self.log.info(f"✅ 异步任务已创建 (当前任务数：{len(self.background_tasks)})")

            # 立即返回，不等待任务完成
            return
        except Exception as e:
            self.log.error(f"创建异步任务失败：{e}", exc_info=True)

    async def _process_hot_title_async(self, hot_title: dict):
        """
        实际处理热榜变化的异步任务。
        包含调用发布器生成内容并发布，发布成功与否均有日志记录。

        :param hot_title: 热榜项字典
        """
        try:
            # 确保发布页面已准备就绪
            await self._ensure_publish_page()

            self.log.info(f"📝 开始生成并发布内容：{hot_title['title']}")
            result = await self.publisher.generate_and_publish(hot_title)

            if result:
                self.log.info(f"✅ 文章发布成功：{hot_title['title']}")
            else:
                self.log.error(f"❌ 文章发布失败：{hot_title['title']}")

        except Exception as e:
            self.log.error(f"❌ 处理热榜变化失败：{e}", exc_info=True)

    async def publish_content(self, content: Dict[str, Any], url: str = None) -> bool:
        """
        发布内容到知乎的指定问题。

        :param content: 内容字典，必须包含 'title', 'content'，可选 'images' 等
        :param url: 目标问题的链接（例如 https://www.zhihu.com/question/xxxxxx/answer/xxxxxx）
        :return: bool - 发布是否成功
        """
        await self._ensure_publish_page()

        if not self.publisher:
            self.log.error("⚠️ 发布器未初始化")
            return False

        return await self.publisher.publish_content(content, url)

    async def get_hot_list(self, start_index: int, end_index: int) -> list:
        """
        获取知乎热榜数据。

        :param start_index: 起始索引（从1开始）
        :param end_index: 结束索引（包含）
        :return: 热榜数据列表，每个元素为包含 'title', 'url', 'hot' 等信息的字典
        """
        if not self.monitor:
            self.log.error("监控器未初始化")
            return []

        return await self.monitor.get_hot_list(start_index, end_index)

    async def run_monitor(self) -> None:
        """
        启动热榜监控循环。
        需要先通过 `start_index` 和 `end_index` 设置监控范围（已在 __init__ 中默认设置）。
        监控器将不断检查热榜变化，一旦发现指定范围内的项发生变化，就触发回调。
        """
        await self._ensure_monitor_page()

        if not self.monitor:
            self.log.error("⚠️ 监控器未初始化")
            return

        # 设置监控范围（起始和结束索引）
        self.monitor.set_monitor_range(
            start_index=self.start_index,
            end_index=self.end_index
        )

        # 启动单次检查循环（内部会持续循环直到手动停止）
        # hot_titles_file 用于持久化上一次的热榜数据，便于对比变化
        await self.monitor.run_single_check(
            hot_titles_file=r"D:\pythonproject\Ai_Blogger\app\Bloggers\ZhihuBlogger\hot_titles.json"
        )

    async def close(self) -> None:
        """
        关闭平台资源，包括：
        - 等待所有后台任务完成（最多等待15秒，超时则取消）
        - 关闭监控页面和发布页面
        """
        self.log.info(f"正在关闭 {self.platform_name}，当前有 {len(self.background_tasks)} 个后台任务...")

        # 等待所有后台任务完成
        if self.background_tasks:
            try:
                done, pending = await asyncio.wait(
                    self.background_tasks,
                    timeout=15.0,
                    return_when=asyncio.ALL_COMPLETED
                )

                # 如果还有未完成的任务，取消它们
                if pending:
                    self.log.warning(f"⚠️  有 {len(pending)} 个任务超时，正在强制取消...")
                    for task in pending:
                        task.cancel()
                        self.log.debug(f"已取消任务：{task}")

                    # 等待取消完成（最多再等 3 秒）
                    try:
                        await asyncio.wait_for(
                            asyncio.gather(*pending, return_exceptions=True),
                            timeout=3.0
                        )
                    except asyncio.TimeoutError:
                        self.log.warning("⚠️  等待任务取消超时")

                    self.log.info(f"✅ 后台任务已清理：完成 {len(done)} 个，取消 {len(pending)} 个")
                else:
                    self.log.info(f"✅ 所有后台任务已完成 ({len(done)} 个)")

            except Exception as e:
                self.log.error(f"等待后台任务失败：{e}", exc_info=True)

        # 关闭监控页面
        if hasattr(self, 'monitor_page') and self.monitor_page:
            try:
                self.log.info("🔒 正在关闭监控页面...")
                await asyncio.wait_for(self.monitor_page.close(), timeout=10.0)
                self.log.info("✅ 监控页面已关闭")
            except Exception as e:
                self.log.warning(f"⚠️  关闭监控页面失败：{e}")

        # 关闭发布页面（注意属性名应为 publish_page，原代码中误写为 publisher_page，保留原样）
        if hasattr(self, 'publisher_page') and self.publisher_page:
            try:
                self.log.info("🔒 正在关闭发布页面...")
                await asyncio.wait_for(self.publisher_page.close(), timeout=10.0)
                self.log.info("✅ 发布页面已关闭")
            except Exception as e:
                self.log.warning(f"⚠️  关闭发布页面失败：{e}")

        self.log.info(f"✅ {self.platform_name} 所有资源已关闭")
