import time
import json
import os
import asyncio
from enum import Enum, auto
from typing import Dict, Any, Optional, List, Literal

from playwright.sync_api import Page
from playwright.async_api import BrowserContext

from app.core.config_manager import config
from app.Bloggers.BasePlatform import BasePlatform

PLATFORM_MODE_MONITOR_ONLY = "monitor_only"  # 只监控
PLATFORM_MODE_PUBLISH_ONLY = "publish_only"  # 只发布
PLATFORM_MODE_MONITOR_AND_PUBLISH = "monitor_and_publish"  # 监控并发布


class WeiboAsyncControl(BasePlatform):
    """
    异步版本的微博平台控制器 - 模块化设计，支持多种运行模式

    核心特性:
    1. 三种运行模式：只监控、只发布、监控并发布
    2. 懒加载：按需初始化组件和页面
    3. 智能登录：全局只登录一次，自动共享状态
    4. 独立页面：监控和发布使用不同页面，互不干扰
    5. 优雅关闭：等待后台任务完成，资源清理完善
    """

    def __init__(self, context: BrowserContext, md_path: str, mode: str = None, user_data_dir: str = None):
        """
        初始化微博异步控制器。

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

        super().__init__(context, md_path, mode, user_data_dir)

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
        平台主运行方法- 根据模式执行不同的逻辑

        :param check_interval:  监控循环间隔（秒），默认 600 秒
        :return:
        """
        if self.mode == PLATFORM_MODE_MONITOR_ONLY:
            self.log.info("🚀 启动只监控热榜模式")
            await self._only_monitor(check_interval)
        elif self.mode == PLATFORM_MODE_PUBLISH_ONLY:
            self.log.info("🚀 启动只发布模式")
        elif self.mode == PLATFORM_MODE_MONITOR_AND_PUBLISH:
            self.log.info("🚀 启动监控并发布模式")

    async def _only_monitor(self, check_interval: int):
        """
        只监控模式下的逻辑（支持循环监控）

        :param check_interval: 监控循环间隔（秒）
        :return:
        """
        try:
            self.log.info(f"🚀 初始化微博平台，模式：{self.mode}")
            from app.Bloggers.WeiboBlogger.Monitor import WeiboMonitor
            self.monitor = WeiboMonitor(self.context)
            await self._ensure_monitor_page()
            self.log.info("✅ 微博监控器已就绪")

            # 设置监控范围
            self.monitor.set_monitor_range(
                start_index=self.start_index,
                end_index=self.end_index
            )

            # 只监控模式：注册一个仅记录日志的回调
            self.monitor.on_change(self.on_monitor_only_change)
            self.log.info("ℹ️ 只监控模式：检测到变化时仅记录日志，不自动发布")

            self.log.info(f"🔍 开始监控热榜（范围：{self.start_index}-{self.end_index}，间隔：{check_interval}秒）")
            # 启动监控循环
            await self.monitor.run_monitor(check_interval=check_interval)

        except Exception as e:
            self.log.error(f"🚀 初始化微博平台失败，错误信息：{e}")
            raise e

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
            pass
        except Exception as e:
            self.log.error(f"🚀 初始化微博发布平台失败，错误信息：{e}")
            raise e

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
            await self.monitor.init()
            self._monitor_initialized = True

            self.log.info("✅ 监控页面已就绪")

        return self.monitor_page
