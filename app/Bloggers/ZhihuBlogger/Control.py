import asyncio
from typing import Dict, Any, Optional, List
from enum import Enum

from playwright.async_api import Page, BrowserContext

from app.Bloggers.BasePlatform import BasePlatform

PLATFORM_MODE_MONITOR_ONLY = "monitor_only"
PLATFORM_MODE_PUBLISH_ONLY = "publish_only"
PLATFORM_MODE_MONITOR_AND_PUBLISH = "monitor_and_publish"


class ZhihuPublishType(Enum):
    """知乎发布类型枚举"""
    ANSWER = "answer"
    ARTICLE = "article"


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
        control = ZhihuAsyncControl(context, md_path, mode=PLATFORM_MODE_MONITOR_ONLY)
        await control.run()

        # 发布回答
        control = ZhihuAsyncControl(context, md_path, mode=PLATFORM_MODE_PUBLISH_ONLY,
                                   publish_type=ZhihuPublishType.ANSWER)
        await control.init()
        await control.publish_content(content, url)

        # 发布文章
        control = ZhihuAsyncControl(context, md_path, mode=PLATFORM_MODE_PUBLISH_ONLY,
                                   publish_type=ZhihuPublishType.ARTICLE)
        await control.init()
        await control.publish_article(title, md_path, image_path)

        # 监控并自动发布
        control = ZhihuAsyncControl(context, md_path, mode=PLATFORM_MODE_MONITOR_AND_PUBLISH,
                                   publish_type=ZhihuPublishType.ANSWER)
        await control.run()
    """

    def __init__(self, context: BrowserContext, md_path: str, mode: str = None,
                 user_data_dir: str = None,
                 publish_type: ZhihuPublishType = ZhihuPublishType.ANSWER):
        """
        初始化控制器

        :param context: 浏览器上下文
        :param md_path: Markdown 文件路径
        :param mode: 运行模式
        :param user_data_dir: 用户数据目录
        :param publish_type: 发布类型
        """
        self.mode = mode
        self.publish_type = publish_type

        if mode is None:
            self._need_monitor = False
            self._need_publish = False
        else:
            self._need_monitor = mode in (PLATFORM_MODE_MONITOR_ONLY, PLATFORM_MODE_MONITOR_AND_PUBLISH)
            self._need_publish = mode in (PLATFORM_MODE_PUBLISH_ONLY, PLATFORM_MODE_MONITOR_AND_PUBLISH)

        super().__init__(platform_name="zhihu", context=context, md_path=md_path, user_data_dir=user_data_dir)

        self.monitor = None
        self.publisher = None
        self.writer = None

        self.monitor_page: Optional[Page] = None
        self.publish_page: Optional[Page] = None

        self._is_logged_in = False
        self._monitor_initialized = False
        self._publisher_initialized = False
        self._writer_initialized = False

        self.start_index: int = 1
        self.end_index: int = 1

        self.background_tasks: set = set()

    async def run(self, check_interval: int = 600):
        """
        平台主运行方法

        :param check_interval: 监控间隔（秒）
        """
        mode_handlers = {
            PLATFORM_MODE_MONITOR_ONLY: self._run_monitor_only,
            PLATFORM_MODE_PUBLISH_ONLY: self._run_publish_only,
            PLATFORM_MODE_MONITOR_AND_PUBLISH: self._run_monitor_and_publish,
        }

        handler = mode_handlers.get(self.mode)
        if handler:
            await handler(check_interval)
        else:
            self.log.error(f"❌ 未知的运行模式：{self.mode}")

    async def _run_monitor_only(self, check_interval: int):
        """只监控模式"""
        try:
            self.log.info("🚀 启动只监控模式")
            await self._init_monitor()
            await self._start_monitoring(check_interval)
        except Exception as e:
            self.log.error(f"❌ 监控模式失败：{e}", exc_info=True)
            raise

    async def _run_publish_only(self, check_interval: int = 0):
        """只发布模式"""
        try:
            self.log.info("🚀 启动只发布模式")
            await self._init_publisher()
            await self._init_writer()
            self.log.info("✅ 发布器已就绪，等待发布任务...")
        except Exception as e:
            self.log.error(f"❌ 发布模式失败：{e}", exc_info=True)
            raise

    async def _run_monitor_and_publish(self, check_interval: int):
        """监控并发布模式"""
        try:
            self.log.info("🚀 启动监控并发布模式")
            await self._init_monitor()
            await self._init_publisher()
            await self._init_writer()
            await self._start_auto_publish_monitoring(check_interval)
        except Exception as e:
            self.log.error(f"❌ 监控并发布模式失败：{e}", exc_info=True)
            raise

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

    async def _ensure_monitor_page(self) -> Page:
        """确保监控页面已创建"""
        if not self._need_monitor:
            raise RuntimeError("当前模式不需要监控功能")

        if self.monitor_page is None or self.monitor_page.is_closed():
            self.log.info("📄 创建监控页面...")
            self.monitor_page = await self.context.new_page()

            if not self._is_logged_in:
                await self._ensure_logged_in()

            self.monitor.page = self.monitor_page
            await self.monitor.init()
            self._monitor_initialized = True
            self.log.info("✅ 监控页面已就绪")

        return self.monitor_page

    async def _ensure_publish_page(self) -> Page:
        """确保发布页面已创建"""
        if not self._need_publish:
            raise RuntimeError("当前模式不需要发布功能")

        if self.publish_page is None or self.publish_page.is_closed():
            self.log.info(f"📄 创建发布页面（类型：{self.publish_type.value}）...")
            self.publish_page = await self.context.new_page()

            if not self._is_logged_in:
                await self._ensure_logged_in()

            self.publisher.page = self.publish_page
            await self.publisher.init()
            self._publisher_initialized = True
            self.log.info(f"✅ 发布页面已就绪（类型：{self.publish_type.value}）")

        return self.publish_page

    async def _start_monitoring(self, check_interval: int):
        """启动监控循环"""
        self.monitor.set_monitor_range(
            start_index=self.start_index,
            end_index=self.end_index
        )

        self.monitor.on_change(self._on_monitor_only_change)
        self.log.info(f"🔍 开始监控热榜（范围：{self.start_index}-{self.end_index}，间隔：{check_interval}秒）")

        await self.monitor.run_monitor(
            hot_titles_file=self.hot_titles_file,
            check_interval=check_interval,
            Get_Hot_Class=self.monitor.Zhihu_GetHot
        )

    async def _start_auto_publish_monitoring(self, check_interval: int):
        """启动监控并自动发布"""
        self.monitor.set_monitor_range(
            start_index=self.start_index,
            end_index=self.end_index
        )

        self.monitor.on_change(self._on_hot_title_change)
        self.log.info("✅ 已注册热榜变化自动发布回调")
        self.log.info(f"🔍 开始监控并发布（范围：{self.start_index}-{self.end_index}，间隔：{check_interval}秒）")

        await self.monitor.run_monitor(
            hot_titles_file=self.hot_titles_file,
            check_interval=check_interval,
            Get_Hot_Class=self.monitor.Zhihu_GetHot
        )

    async def _on_monitor_only_change(self, hot_title: dict):
        """只监控模式下的回调 - 仅记录日志"""
        self.log.info(f"🔔 [只监控] 热榜变化：{hot_title['title']}")
        self.log.info(f"   排名：{hot_title.get('rank', 'N/A')}")
        self.log.info(f"   热度：{hot_title.get('hot', 'N/A')}")
        self.log.info(f"   链接：{hot_title.get('url', 'N/A')}")

    async def _on_hot_title_change(self, hot_title: dict):
        """热榜变化回调 - 自动发布"""
        try:
            self.log.info(f"🔔 检测到热榜变化：{hot_title['title']}")

            task = asyncio.create_task(self._process_hot_title_async(hot_title))
            self.background_tasks.add(task)
            task.add_done_callback(lambda t: self.background_tasks.discard(t))

            self.log.info(f"✅ 异步任务已创建 (当前任务数：{len(self.background_tasks)})")
        except Exception as e:
            self.log.error(f"❌ 创建异步任务失败：{e}", exc_info=True)

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
            write_text = WriteZhihuText(model_name=self.publisher.model_name)

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
                "href": hot_title.get("url", None),
                "md_path": md_path,
                "title": json_data.get("title", None)
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

    async def get_hot_list(self, start_index: int = 1, end_index: int = 50) -> list:
        """
        获取热榜数据

        :param start_index: 起始索引
        :param end_index: 结束索引
        :return: 热榜列表
        """
        if not self._need_monitor:
            self.log.error("❌ 当前模式不支持监控功能")
            return []

        await self._ensure_monitor_page()

        if not self.monitor:
            self.log.error("⚠️ 监控器未初始化")
            return []

        return await self.monitor.get_hot_list(start_index, end_index)

    async def close(self) -> None:
        """关闭平台资源"""
        self.log.info(f"⏳ 正在关闭知乎平台，当前有 {len(self.background_tasks)} 个后台任务...")

        if self.background_tasks:
            await self._wait_for_background_tasks()

        await self._close_page(self.monitor_page, "监控页面")
        await self._close_page(self.publish_page, "发布页面")

        self.log.info("✅ 知乎平台所有资源已关闭")

    async def _wait_for_background_tasks(self, timeout: float = 15.0):
        """等待后台任务完成"""
        try:
            done, pending = await asyncio.wait(
                self.background_tasks,
                timeout=timeout,
                return_when=asyncio.ALL_COMPLETED
            )

            if pending:
                self.log.warning(f"⚠️  {len(pending)} 个任务超时，正在强制取消...")
                for task in pending:
                    task.cancel()

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

    async def _close_page(self, page: Optional[Page], page_name: str):
        """关闭页面"""
        if page and not page.is_closed():
            try:
                self.log.info(f"🔒 正在关闭{page_name}...")
                await asyncio.wait_for(page.close(), timeout=10.0)
                self.log.info(f"✅ {page_name}已关闭")
            except Exception as e:
                self.log.warning(f"⚠️  关闭{page_name}失败：{e}")

    @property
    def status(self) -> Dict[str, Any]:
        """获取平台当前状态"""
        return {
            'mode': self.mode,
            'publish_type': self.publish_type.value,
            'is_logged_in': self._is_logged_in,
            'monitor_initialized': self._monitor_initialized,
            'publisher_initialized': self._publisher_initialized,
            'writer_initialized': self._writer_initialized,
            'monitor_page_active': self.monitor_page is not None and not self.monitor_page.is_closed(),
            'publish_page_active': self.publish_page is not None and not self.publish_page.is_closed(),
            'background_tasks': len(self.background_tasks)
        }
