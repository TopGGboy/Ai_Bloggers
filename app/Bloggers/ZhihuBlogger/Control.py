import time
import json
import os
import asyncio
from enum import Enum, auto
from typing import Dict, Any, Optional, List, Literal

from playwright.sync_api import Page
from playwright.async_api import BrowserContext

from app.tools.LoggingConfig import LoggingConfig
from app.core.config_manager import config
from app.Bloggers.BasePlatform import BasePlatform

PLATFORM_MODE_MONITOR_ONLY = "monitor_only"  # 只监控
PLATFORM_MODE_PUBLISH_ONLY = "publish_only"  # 只发布
PLATFORM_MODE_MONITOR_AND_PUBLISH = "monitor_and_publish"  # 监控并发布


class ZhihuAsyncControl(BasePlatform):
    """
    异步版本的知乎平台控制器 - 模块化设计，支持多种运行模式

    核心特性:
    1. 三种运行模式：只监控、只发布、监控并发布
    2. 懒加载：按需初始化组件和页面
    3. 智能登录：全局只登录一次，自动共享状态
    4. 独立页面：监控和发布使用不同页面，互不干扰
    5. 优雅关闭：等待后台任务完成，资源清理完善

    使用示例:
        # 模式 1：只监控（不需要登录）
        control = ZhihuAsyncControl(context, md_path, mode=OperationMode.MONITOR_ONLY)
        await control.init()
        await control.run_monitor()

        # 模式 2：只发布（需要登录）
        control = ZhihuAsyncControl(context, md_path, mode=OperationMode.PUBLISH_ONLY)
        await control.init()
        await control.publish_content(content, url)

        # 模式 3：监控并发布（自动联动）
        control = ZhihuAsyncControl(context, md_path, mode=OperationMode.MONITOR_AND_PUBLISH)
        await control.init()
        await control.start_auto_publish()  # 启动自动发布
    """

    def __init__(self, context: BrowserContext, md_path: str, mode: str = None, user_data_dir: str = None):
        """
        初始化知乎异步控制器。

        :param context: Playwright 的浏览器上下文，用于创建新页面
        :param md_path: Markdown 文件的路径，发布器需要用到的资源
        :param mode: 运行模式，默认为监控并发布
        """
        # 运行模式配置
        self.mode = mode

        if mode is None:
            self._need_monitor = False
            self._need_publish = False
            self._auto_publish = False
        else:
            self._need_monitor = mode in (PLATFORM_MODE_MONITOR_ONLY, PLATFORM_MODE_MONITOR_AND_PUBLISH)
            self._need_publish = mode in (PLATFORM_MODE_PUBLISH_ONLY, PLATFORM_MODE_MONITOR_AND_PUBLISH)
            self._auto_publish = mode == PLATFORM_MODE_MONITOR_AND_PUBLISH

        super().__init__(context, md_path, user_data_dir)

        # 监控器和发布器实例，懒加载初始化
        self.monitor = None
        self.publisher = None

        # 监控页面和发布页面，各自独立，避免互相干扰
        self.monitor_page: Optional[Page] = None
        self.publish_page: Optional[Page] = None

        # 状态管理
        self._is_logged_in = False
        self._monitor_initialized = False
        self._publisher_initialized = False

        # 监控配置
        self.start_index: int = 1
        self.end_index: int = 1
        self.hot_titles: Optional[List] = None

        # 异步任务管理
        self.background_tasks: set = set()

        # 重试配置
        self.retry_config = {"login": 3, "publish": 2, "get_hot": 2}

    async def run(self, check_interval: int = 600):
        """
        平台主运行方法 - 根据模式执行不同的逻辑

        :param check_interval: 监控循环间隔（秒），默认 600 秒
        :return:
        """
        if self.mode == PLATFORM_MODE_MONITOR_ONLY:
            self.log.info("🚀 启动只监控模式")
            await self._only_monitor(check_interval)
        elif self.mode == PLATFORM_MODE_PUBLISH_ONLY:
            self.log.info("🚀 启动只发布模式")
            await self._only_publish()
        elif self.mode == PLATFORM_MODE_MONITOR_AND_PUBLISH:
            self.log.info("🚀 启动监控并发布模式")
            await self._monitor_and_publish(check_interval)

    async def _only_monitor(self, check_interval: int = 600):
        """
        只监控模式下的运行逻辑（支持循环监控）

        :param check_interval: 监控循环间隔（秒）
        """
        try:
            self.log.info(f"🚀 初始化知乎平台，模式：{self.mode}")
            from app.Bloggers.ZhihuBlogger.Monitor import ZhihuMonitor
            self.monitor = ZhihuMonitor(context=self.context)
            await self._ensure_monitor_page()
            self.log.info("✅ 监控器已初始化")

            # 设置监控范围
            self.monitor.set_monitor_range(
                start_index=self.start_index,
                end_index=self.end_index
            )

            # 只监控模式：注册一个仅记录日志的回调
            self.monitor.on_change(self._on_monitor_only_change)
            self.log.info("ℹ️ 只监控模式：检测到变化时仅记录日志，不自动发布")

            # 启动监控循环（持续运行）
            self.log.info(f"🔍 开始监控热榜（范围：{self.start_index}-{self.end_index}，间隔：{check_interval}秒）")
            await self.run_monitor(
                check_interval=check_interval,
                hot_titles_file=r"D:\pythonproject\Ai_Blogger\app\Bloggers\ZhihuBlogger\hot_titles.json"
            )

        except Exception as e:
            self.log.error(f"❌ 监控模式运行失败：{e}", exc_info=True)
            raise

    async def _on_monitor_only_change(self, hot_title: dict):
        """
        只监控模式下的变化回调函数 - 仅记录日志，不发布文章

        :param hot_title: 发生变化的热榜项字典
        """
        self.log.info(f"🔔 [只监控模式] 检测到热榜变化：{hot_title['title']}")
        self.log.info(f"   排名：{hot_title.get('rank', 'N/A')}")
        self.log.info(f"   热度：{hot_title.get('hot', 'N/A')}")
        self.log.info(f"   链接：{hot_title.get('url', 'N/A')}")
        # 注意：这里不调用发布器，仅记录日志

    async def _only_publish(self):
        """
        只发布模式下的运行逻辑

        流程：
        1. 初始化发布页面
        2. 等待内容发布任务
        3. 通过 publish_content 接口发布内容
        """
        try:
            self.log.info(f"🚀 初始化知乎平台，模式：{self.mode}")
            from app.Bloggers.ZhihuBlogger.Publisher import ZhihuPublisher
            self.monitor = ZhihuPublisher(context=self.context, md_path=self.md_path)
            await self._ensure_publish_page()
            self.log.info("✅ 发布器已初始化")

            self.log.info("✅ 发布模式已就绪，等待发布任务...")

            # 只发布模式下，通过外部调用 publish_content 来发布内容
            # 这里可以添加一个等待循环，或者由外部控制发布时机
            # 示例：等待用户输入或外部信号

        except Exception as e:
            self.log.error(f"❌ 发布模式运行失败：{e}", exc_info=True)
            raise

    async def _monitor_and_publish(self, check_interval: int = 600):
        """
        监控并发布模式下的运行逻辑（支持循环监控）

        :param check_interval: 监控循环间隔（秒）

        流程：
        1. 初始化监控页面和发布页面
        2. 设置热榜变化回调
        3. 启动监控循环
        4. 当检测到热榜变化时，自动触发内容生成和发布
        """
        try:
            self.log.info(f"🚀 初始化知乎平台，模式：{self.mode}")
            from app.Bloggers.ZhihuBlogger.Publisher import ZhihuPublisher
            from app.Bloggers.ZhihuBlogger.Monitor import ZhihuMonitor
            self.monitor = ZhihuPublisher(context=self.context, md_path=self.md_path)
            self.monitor = ZhihuMonitor(context=self.context)

            # 确保监控和发布页面都已准备
            await self._ensure_monitor_page()
            await self._ensure_publish_page()

            self.log.info("✅ 监控器和发布器已初始化")

            self.monitor.on_change(self._on_hot_title_change)
            self.log.info("✅ 已注册热榜变化自动发布回调")

            # 启动监控循环（检测到变化会自动触发回调进行发布）
            self.log.info(f"🔍 开始监控并发布（范围：{self.start_index}-{self.end_index}，间隔：{check_interval}秒）")
            await self.run_monitor(
                check_interval=check_interval,
                hot_titles_file=r"D:\pythonproject\Ai_Blogger\app\Bloggers\ZhihuBlogger\hot_titles.json"
            )

        except Exception as e:
            self.log.error(f"❌ 监控并发布模式运行失败：{e}", exc_info=True)
            raise

    async def _ensure_logged_in(self):
        """
        确保已登录（全局只登录一次）

        登录在一个临时页面中执行，完成后关闭该页面
        登录状态通过 Cookie 在所有页面间共享
        """
        if not self._is_logged_in:
            self.log.info("⏳ 正在登录知乎...")

            # 创建一个临时页面用于登录
            temp_page = await self.context.new_page()
            try:
                from app.Bloggers.ZhihuBlogger.Login import AsyncZhihuLogin
                login = AsyncZhihuLogin(page=temp_page, user_data_dir=self.user_data_dir)
                await login.login()
                await temp_page.close()  # 登录完成后关闭临时页面
                self._is_logged_in = True
                self.log.info("✅ 登录成功（登录状态将在所有页面间共享）")
            finally:
                await temp_page.close()
        else:
            self.log.debug("✨ 已经登录过，跳过登录步骤")

    async def _ensure_monitor_page(self) -> Page:
        """
        确保监控页面已创建并返回该页面。
        如果页面不存在或已关闭，则新建页面并执行登录（如果需要）。

        :return: 可用的监控页面对象
        """
        if not self._need_monitor:
            raise RuntimeError("当前模式不需要监控功能")

        if self.monitor_page is None or self.monitor_page.is_closed():
            self.log.info("📄 创建监控页面...")
            self.monitor_page = await self.context.new_page()

            # 首次监控才需要登录
            if not self._is_logged_in:
                await self._ensure_logged_in()

            # 关联到监控器并初始化
            self.monitor.page = self.monitor_page
            await self.monitor.init_without_new_page()
            self._monitor_initialized = True

            self.log.info("✅ 监控页面已就绪")

        return self.monitor_page

    async def _ensure_publish_page(self) -> Page:
        """
        确保发布页面已创建并返回该页面。
        如果页面不存在或已关闭，则新建页面并执行登录。

        :return: 可用的发布页面对象
        """
        if not self._need_publish:
            raise RuntimeError("当前模式不需要发布功能")

        if self.publish_page is None or self.publish_page.is_closed():
            self.log.info("📄 创建发布页面...")
            self.publish_page = await self.context.new_page()

            # 首次创建发布页面时才需要登录
            if not self._is_logged_in:
                await self._ensure_logged_in()

            # 关联到发布器并初始化
            self.publisher.page = self.publish_page
            await self.publisher.init_without_new_page()
            self._publisher_initialized = True

            self.log.info("✅ 发布页面已就绪")

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
            self.log.error(f"❌ 创建异步任务失败：{e}", exc_info=True)

    async def _process_hot_title_async(self, hot_title: dict) -> bool:
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
        if not self._need_publish:
            self.log.error("❌ 当前模式不支持发布功能")
            return False

        # 确保发布页面已准备就绪
        await self._ensure_publish_page()

        if not self.publisher:
            self.log.error("⚠️ 发布器未初始化")
            return False

        return await self.publisher.publish_answer(content, url)

    async def get_hot_list(self, start_index: int = 1, end_index: int = 50) -> list:
        """
        获取知乎热榜数据。

        :param start_index: 起始索引（从1开始）
        :param end_index: 结束索引（包含）
        :return: 热榜数据列表，每个元素为包含 'title', 'url', 'hot' 等信息的字典
        """
        if not self._need_monitor:
            self.log.error("❌ 当前模式不支持监控功能")
            return []

            # 确保监控页面存在
        await self._ensure_monitor_page()

        if not self.monitor:
            self.log.error("⚠️ 监控器未初始化")
            return []

        return await self.monitor.get_hot_list(start_index, end_index)

    async def run_monitor(self, check_interval: int = 600, hot_titles_file: str = None) -> None:
        """
        启动热榜监控循环。
        需要先通过 `start_index` 和 `end_index` 设置监控范围（已在 __init__ 中默认设置）。
        监控器将不断检查热榜变化，一旦发现指定范围内的项发生变化，就触发回调。
        """
        if not self._need_monitor:
            self.log.error("❌ 当前模式不支持监控功能")
            return

        # 确保监控页面存在
        await self._ensure_monitor_page()

        if not self.monitor:
            self.log.error("⚠️ 监控器未初始化")
            return

        # 设置监控范围（起始和结束索引）
        self.monitor.set_monitor_range(
            start_index=self.start_index,
            end_index=self.end_index
        )

        self.log.info(f"🔍 开始监控热榜（范围：{self.start_index}-{self.end_index}）")
        await self.monitor.run_monitor(
            hot_titles_file=r"D:\pythonproject\Ai_Blogger\app\Bloggers\ZhihuBlogger\hot_titles.json",
            check_interval=check_interval
        )

    async def close(self) -> None:
        """
        关闭平台资源，包括：
        - 等待所有后台任务完成（最多等待15秒，超时则取消）
        - 关闭监控页面和发布页面
        """
        self.log.info(f"⏳ 正在关闭 {self.platform_name}，当前有 {len(self.background_tasks)} 个后台任务...")

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

    @property
    def status(self) -> Dict[str, Any]:
        """获取平台当前状态"""
        return {
            'mode': self.mode,
            'is_logged_in': self._is_logged_in,
            'monitor_initialized': self._monitor_initialized,
            'publisher_initialized': self._publisher_initialized,
            'monitor_page_active': self.monitor_page is not None and not self.monitor_page.is_closed(),
            'publish_page_active': self.publish_page is not None and not self.publish_page.is_closed(),
            'background_tasks': len(self.background_tasks)
        }
