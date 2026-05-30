from abc import ABC, abstractmethod
from playwright.async_api import BrowserContext, Page
import logging
from typing import Dict, Any, Optional
import asyncio

from app.core.config_manager import config
from app.Bloggers.PlatformEnums import PlatformMode
from app.tools.LoggingConfig import LoggingConfig


class BasePlatform(ABC):
    """
    平台基类 - 定义所有平台的统一接口

    采用模板方法模式：
    - 基类定义运行流程（骨架）
    - 子类实现平台特定的步骤
    """

    def __init__(self, platform_name: str, context: BrowserContext,
                 mode: PlatformMode = PlatformMode.MONITOR_AND_PUBLISH,
                 user_data_dir: str = None, publish_type: Any = None):
        """
        初始化平台

        Args:
            platform_name: 平台名称（用于读取配置）
            context: 独立的浏览器上下文（每个平台一个）
            mode: 运行模式
            user_data_dir: 用户数据目录
            publish_type: 发布类型
        """
        self.platform_name = platform_name
        self.user_data_dir = user_data_dir
        self.context = context
        self.page: Optional[Page] = None
        self.mode = mode
        self.publish_type = publish_type

        # 日志
        self.log = LoggingConfig(log_file_path=config.logfile_path, log_level=config.log_level).get_logger(
            self.__class__.__name__)

        # 从配置加载平台特定参数
        self.hot_titles_file = config.platforms[platform_name]["paths"]["hot_title_file"]
        self.check_interval = config.platforms[platform_name]["check_interval"]

        # 模式判断
        if mode is None:
            self._need_monitor = False
            self._need_publish = False
        else:
            self._need_monitor = mode in (PlatformMode.MONITOR_ONLY, PlatformMode.MONITOR_AND_PUBLISH)
            self._need_publish = mode in (PlatformMode.PUBLISH_ONLY, PlatformMode.MONITOR_AND_PUBLISH)

        # 组件实例（由子类初始化管理）
        self.monitor = None
        self.publisher = None
        self.writer = None

        # 页面实例
        self.monitor_page: Optional[Page] = None
        self.publish_page: Optional[Page] = None

        # 状态标记
        self._is_logged_in = False
        self._monitor_initialized = False
        self._publisher_initialized = False
        self._writer_initialized = False

        # 初始化索引
        self.start_index: int = 1
        self.end_index: int = 1

        # 后台任务管理
        self.background_tasks: set = set()

    async def run(self) -> None:
        """
        平台主运行方法 - 模板方法，定义运行流程
        """
        mode_handlers = {
            PlatformMode.MONITOR_ONLY: self.__run_monitor_only,
            PlatformMode.PUBLISH_ONLY: self.__run_publish_only,
            PlatformMode.MONITOR_AND_PUBLISH: self.__run_monitor_and_publish,
        }

        handler = mode_handlers.get(PlatformMode(self.mode))
        if handler:
            await handler()
        else:
            self.log.error(f"❌ 未知的运行模式：{self.mode}")

    async def __run_monitor_only(self):
        """只监控模式"""
        try:
            self.log.info("🚀 启动只监控模式")
            await self._init_monitor()
            await self._start_monitoring(self.check_interval)
        except Exception as e:
            self.log.error(f"❌ 监控模式失败：{e}", exc_info=True)
            raise

    async def __run_publish_only(self):
        """只发布模式"""
        try:
            self.log.info("🚀 启动只发布模式")
            await self._init_publisher()
            await self._init_writer()
            self.log.info("✅ 发布器已就绪，等待发布任务...")
        except Exception as e:
            self.log.error(f"❌ 发布模式失败：{e}", exc_info=True)
            raise

    async def __run_monitor_and_publish(self):
        """监控并发布模式"""
        try:
            self.log.info("🚀 启动监控并发布模式")
            await self._init_monitor()
            await self._init_publisher()
            await self._init_writer()
            await self._start_auto_publish_monitoring(self.check_interval)
        except Exception as e:
            self.log.error(f"❌ 监控并发布模式失败：{e}", exc_info=True)
            raise

    @abstractmethod
    async def _init_monitor(self) -> None:
        """
        初始化监控器（由子类实现）

        子类需要在此方法中：
        1. 创建监控器实例并赋值给 self.monitor
        2. 调用 _ensure_monitor_page() 确保页面就绪
        3. 设置 _monitor_initialized = True
        """
        pass

    @abstractmethod
    async def _init_publisher(self) -> None:
        """
        初始化发布器（由子类实现）

        子类需要在此方法中：
        1. 创建发布器实例并赋值给 self.publisher
        2. 调用 _ensure_publish_page() 确保页面就绪
        3. 设置 _publisher_initialized = True
        """
        pass

    @abstractmethod
    async def _init_writer(self) -> None:
        """
        初始化写作器（由子类实现）

        子类需要在此方法中：
        1. 创建写作器实例并赋值给 self.writer
        2. 设置 _writer_initialized = True
        """
        pass

    @abstractmethod
    async def _ensure_logged_in(self) -> None:
        """
        确保已登录（由子类实现）

        子类需要在此方法中：
        1. 检查是否已登录
        2. 如未登录，执行登录流程
        3. 设置 _is_logged_in = True
        """
        pass

    async def _start_monitoring(self, check_interval: int) -> None:
        """启动监控循环"""
        self.monitor.set_monitor_range(
            start_index=self.start_index,
            end_index=self.end_index
        )

        self.monitor.on_change(self._on_monitor_only_change)
        self.log.info(f"🔍 开始监控热榜（范围：{self.start_index}-{self.end_index}，间隔：{check_interval}秒）")

        await self.monitor.run_monitor(
            hot_titles_file=self.hot_titles_file,
            check_interval=check_interval
        )

    async def _start_auto_publish_monitoring(self, check_interval: int) -> None:
        """启动监控并自动发布（通用实现）"""
        self.monitor.set_monitor_range(
            start_index=self.start_index,
            end_index=self.end_index
        )

        self.monitor.on_change(self._on_hot_title_change)
        self.log.info("✅ 已注册热榜变化自动发布回调")
        self.log.info(f"🔍 开始监控并发布（范围：{self.start_index}-{self.end_index}，间隔：{check_interval}秒）")

        await self.monitor.run_monitor(
            hot_titles_file=self.hot_titles_file,
            check_interval=check_interval
        )

    @abstractmethod
    async def _process_hot_title_async(self, hot_title: dict) -> bool:
        """
        处理热榜变化的异步任务（由子类实现）

        Args:
            hot_title: 热榜项字典

        Returns:
            bool: 处理是否成功
        """
        pass

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

    async def _ensure_monitor_page(self) -> Page:
        """确保监控页面已创建（通用实现，子类可直接使用）

        Returns:
            Page: 监控页面对象
        """
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
        """
        确保发布页面已创建（通用实现，子类可直接使用）

        Returns:
            Page: 发布页面对象
        """
        if not self._need_publish:
            raise RuntimeError("当前模式不需要发布功能")

        if self.publish_page is None or self.publish_page.is_closed():
            self.log.info(f"📄 创建发布页面（类型：{self.publish_type}）...")
            self.publish_page = await self.context.new_page()

            if not self._is_logged_in:
                await self._ensure_logged_in()

            self.publisher.page = self.publish_page
            self._publisher_initialized = True
            self.log.info(f"✅ 发布页面已就绪（类型：{self.publish_type}）")

        return self.publish_page

    async def get_hot_list(self, start_index: int = 1, end_index: int = 50) -> list:
        """
        获取热榜数据（通用实现）

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
        """关闭平台资源（通用实现）"""
        self.log.info(f"⏳ 正在关闭 {self.platform_name} 平台，当前有 {len(self.background_tasks)} 个后台任务...")

        if self.background_tasks:
            await self._wait_for_background_tasks()

        await self._close_page(self.monitor_page, "监控页面")
        await self._close_page(self.publish_page, "发布页面")

        self.log.info(f"✅ {self.platform_name} 平台所有资源已关闭")

    async def _wait_for_background_tasks(self, timeout: float = 15.0):
        """等待后台任务完成（通用实现）"""
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
        """关闭页面（通用实现）"""
        if page and not page.is_closed():
            try:
                self.log.info(f"🔒 正在关闭{page_name}...")
                await asyncio.wait_for(page.close(), timeout=10.0)
                self.log.info(f"✅ {page_name}已关闭")
            except Exception as e:
                self.log.warning(f"⚠️  关闭{page_name}失败：{e}")

    @property
    def status(self) -> Dict[str, Any]:
        """获取平台当前状态（通用实现）"""
        return {
            'platform': self.platform_name,
            'mode': self.mode,
            'publish_type': str(self.publish_type) if self.publish_type else None,
            'is_logged_in': self._is_logged_in,
            'monitor_initialized': self._monitor_initialized,
            'publisher_initialized': self._publisher_initialized,
            'writer_initialized': self._writer_initialized,
            'monitor_page_active': self.monitor_page is not None and not self.monitor_page.is_closed(),
            'publish_page_active': self.publish_page is not None and not self.publish_page.is_closed(),
            'background_tasks': len(self.background_tasks)
        }

    async def random_sleep(self, min_seconds: float = 1.0, max_seconds: float = 3.0) -> None:
        """随机延迟（模拟真人操作）"""
        import random
        delay = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(delay)
        self.log.debug(f"延迟 {delay:.2f}秒")
