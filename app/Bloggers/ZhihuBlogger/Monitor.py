import json
import os
import asyncio
from typing import Optional, List, Callable

from playwright.async_api import Page, BrowserContext
from app.tools.LoggingConfig import LoggingConfig
from app.core.config_manager import config


class ZhihuMonitor:
    """知乎热榜监控器 - 专注于监控热榜变化"""

    def __init__(self, context: BrowserContext):
        """
        初始化监控器

        Args:
            context: Playwright BrowserContext 实例
        """
        self.context = context
        self.page: Optional[Page] = None
        self.Zhihu_GetHot = None

        # 状态配置
        self.url = "https://www.zhihu.com/hot"
        self.start_index: Optional[int] = 1
        self.end_index: Optional[int] = 1
        self.hot_titles: Optional[List] = None

        # 日志
        self.log = LoggingConfig(log_file_path=config.logfile_path, log_level=config.log_level).get_logger(
            self.__class__.__name__)

        # 回调函数（当检测到变化时调用）
        self.on_change_callback: Optional[Callable] = None

    async def init(self) -> None:
        """初始化监控器"""
        try:
            # 创建新页面
            self.page = await self.context.new_page()

            # 初始化获取热榜组件
            from app.Bloggers.ZhihuBlogger.GetHot import AsyncGetHot
            self.Zhihu_GetHot = AsyncGetHot(page=self.page, logging=True)

            self.log.info("知乎监控器初始化成功")

        except Exception as e:
            self.log.error(f"知乎监控器初始化失败：{e}", exc_info=True)
            raise

    async def init_without_new_page(self) -> None:
        """初始化监控器（不创建新 page，使用已有的 page）"""
        try:
            if not self.page:
                self.log.error("页面未初始化")
                raise ValueError("page 必须在使用前初始化")

            # 初始化获取热榜组件
            from app.Bloggers.ZhihuBlogger.GetHot import AsyncGetHot
            self.Zhihu_GetHot = AsyncGetHot(page=self.page, logging=True)

            self.log.info("知乎监控器初始化成功")

        except Exception as e:
            self.log.error(f"知乎监控器初始化失败：{e}", exc_info=True)
            raise

    def set_monitor_range(self, start_index: int, end_index: Optional[int] = None):
        """
        设置监控范围

        Args:
            start_index: 起始索引（从 1 开始）
            end_index: 结束索引（可选，不传则只监控单个）
        """
        self.start_index = start_index
        self.end_index = end_index

    def on_change(self, callback: Callable):
        """
        注册变化检测回调函数

        Args:
            callback: 回调函数，接收参数 (hot_title_dict)
        """
        self.on_change_callback = callback

    async def random_sleep(self, min_seconds: float = 1.0, max_seconds: float = 3.0) -> None:
        """随机延迟（模拟真人操作）"""
        import random
        delay = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(delay)
        self.log.debug(f"延迟 {delay:.2f}秒")

    async def run_single_check(self, hot_titles_file: str = None) -> None:
        """
        执行单次检测

        Args:
            hot_titles_file: 热榜标题保存文件路径
        """
        try:
            self.log.info("▶️ 开始单次检测...")

            if not self.page:
                self.log.error("页面未初始化")
                return

            if hot_titles_file is None:
                hot_titles_file = r"D:\pythonproject\Ai_Blogger\app\Bloggers\ZhihuBlogger\hot_titles.json"

            # 导航到热榜页面
            self.log.info("🌐 正在导航到热榜页面...")
            await self.page.goto(self.url, wait_until="domcontentloaded")
            await self.random_sleep(2, 4)

            # 持久化保存热榜标题
            self.log.info("💾 正在保存热榜标题...")
            await self._save_hot_title(hot_titles_file=hot_titles_file)

            # 检查热榜标题变化
            if self.start_index and self.end_index:
                self.log.info("📊 检查范围热榜变化...")
                await self._check_hot_titles()
            else:
                self.log.info("📍 检查单个热榜变化...")
                await self._check_hot_single_title()

            self.log.info("✅ 单次检测完成")

        except Exception as e:
            self.log.error(f"检测失败：{e}", exc_info=True)
            raise

    async def run_monitor(self, check_interval: int = 600, hot_titles_file: str = None) -> None:
        """
        启动监控循环

        Args:
            check_interval: 检测间隔（秒），默认 600 秒
            hot_titles_file: 热榜标题保存文件路径
        """
        try:
            if not self.page:
                self.log.error("页面未初始化")
                return

            if hot_titles_file is None:
                hot_titles_file = r"D:\pythonproject\Ai_Blogger\app\Bloggers\ZhihuBlogger\hot_titles.json"

            count = 0
            while True:
                count += 1
                self.log.info(f"第 {count} 次检测")

                # 导航到热榜页面
                await self.page.goto(self.url, wait_until="domcontentloaded")
                await self.random_sleep(2, 4)

                # 持久化保存热榜标题
                await self._save_hot_title(hot_titles_file=hot_titles_file)

                # 检查热榜标题变化
                if self.start_index and self.end_index:
                    await self._check_hot_titles()
                else:
                    await self._check_hot_single_title()

                # 每隔指定时间检测一次
                await asyncio.sleep(check_interval)

        except Exception as e:
            self.log.error(f"监控任务失败：{e}", exc_info=True)
            raise

    async def _check_hot_titles(self):
        """检查热榜标题变化（范围模式）"""
        try:
            hot_titles = await self.Zhihu_GetHot.get_hot_title_list(self.start_index, self.end_index)
            if not hot_titles:
                self.log.warning("未获取到热榜数据，跳过检查")
                return

            new_hot_titles = [hot_title['title'] for hot_title in hot_titles]

            # 边界检查，避免索引越界
            max_index = min(len(new_hot_titles), len(self.hot_titles))
            for index in range(max_index):
                new_title = new_hot_titles[index]
                if new_title != self.hot_titles[index]:
                    self.log.info(
                        f"检测到榜单 {self.start_index + index} 发生变化：{self.hot_titles[index]} → {new_title}")
                    self.hot_titles[index] = new_title

                    # 触发回调
                    if self.on_change_callback:
                        # 【关键修改】创建任务后立即返回，不等待
                        task = asyncio.create_task(self.on_change_callback(hot_titles[index]))
                        self.log.debug(f"已创建任务处理变化：{hot_titles[index]['title']}")

                self.log.debug(f"_check_hot_titles 完成，共发现 {max_index} 个变化")

        except Exception as e:
            self.log.error(f"检查热榜范围变化失败：{e}", exc_info=True)

    async def _check_hot_single_title(self):
        """检查单个热榜标题变化"""
        try:
            new_title_list = await self.Zhihu_GetHot.get_hot_title_list(self.start_index, self.start_index)
            if not new_title_list:
                self.log.warning("未获取到单个热榜数据，跳过检查")
                return

            new_title = new_title_list[0]["title"]
            # 空值检查，避免对比 None 报错
            if self.hot_titles and self.hot_titles[0] != new_title:
                self.log.info(f"检测到榜单 {self.start_index} 发生变化：{self.hot_titles[0]} → {new_title}")
                self.hot_titles[0] = new_title

                # 触发回调
                if self.on_change_callback:
                    # 【关键修改】创建任务后立即返回
                    task = asyncio.create_task(self.on_change_callback(new_title_list[0]))
                    self.log.debug(f"已创建任务处理变化：{new_title_list[0]['title']}")

            self.log.debug("_check_hot_single_title 完成")

        except Exception as e:
            self.log.error(f"检查单个热榜变化失败：{e}", exc_info=True)

    async def _save_hot_title(self, hot_titles_file="./hot_titles.json"):
        """持久化保存热榜标题"""
        try:
            # 如果没有传入标题且文件存在，读取历史数据
            if not self.hot_titles and os.path.exists(hot_titles_file):
                with open(hot_titles_file, "r", encoding="utf-8") as f:
                    self.hot_titles = json.load(f)

                # 更严谨的列表长度处理，避免索引越界
                if self.start_index is not None:
                    if not self.end_index:
                        # 单个标题模式
                        if len(self.hot_titles) >= self.start_index:
                            self.hot_titles = [self.hot_titles[self.start_index - 1]]
                        else:
                            self.hot_titles = [None]
                    else:
                        # 范围模式
                        start = self.start_index - 1
                        end = self.end_index
                        self.hot_titles = self.hot_titles[start:end] if len(self.hot_titles) > start else []
                        # 补全空值
                        need_fill = (self.end_index - self.start_index + 1) - len(self.hot_titles)
                        if need_fill > 0:
                            self.hot_titles += [None] * need_fill

            # 如果没有传入标题且文件不存在，创建文件
            elif not self.hot_titles:
                self.hot_titles = []
                with open(hot_titles_file, "w", encoding="utf-8") as f:
                    json.dump([], f, ensure_ascii=False, indent=4)

            # 保存热榜标题到文件
            if self.hot_titles:
                with open(hot_titles_file, 'w', encoding='utf-8') as f:
                    json.dump(self.hot_titles, f, ensure_ascii=False, indent=4)
                self.log.info(f"保存热榜标题成功，共 {len(self.hot_titles)} 个标题")

        except Exception as e:
            self.log.error(f"读取/保存热榜标题文件失败：{e}", exc_info=True)

    async def get_hot_list(self, start_index: int, end_index: int) -> list:
        """
        获取热榜数据

        Args:
            start_index: 起始索引
            end_index: 结束索引

        Returns:
            list: 热榜数据列表
        """
        try:
            if not self.page:
                self.log.error("页面未初始化")
                return []

            hot_titles = await self.Zhihu_GetHot.get_hot_title_list(start_index, end_index)
            return hot_titles

        except Exception as e:
            self.log.error(f"获取热榜失败：{e}", exc_info=True)
            return []
