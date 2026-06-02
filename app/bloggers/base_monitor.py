import asyncio
import json
import os
from abc import ABC, abstractmethod
from playwright.async_api import BrowserContext, Page
from typing import Any, Optional, List, Callable

from app.tools.logging_config import LoggingConfig
from app.core.config_manager import config


class BaseMonitor(ABC):
    """
    监控器基类 - 采用模板方法模式

    设计原则：
    1. 基类定义监控流程骨架
    2. 子类实现平台特定的步骤
    3. 通过钩子方法支持扩展
    """

    def __init__(self, platform_name: str, context: BrowserContext):
        """
初始化监控器

        :param platform_name: 平台名称
        :param context: Playwright 的浏览器上下文
        """
        self.context = context
        self.page: Optional[Page] = None

        # 监控范围
        self.start_index: Optional[int] = 1
        self.end_index: Optional[int] = None

        # 热榜数据
        self.hot_titles: Optional[List] = None

        self.hot_titles_file = config.platforms[platform_name]["paths"]["hot_title_file"]
        self.hot_url = config.platforms[platform_name]["urls"]["hot_list"]

        # 日志
        self.log = LoggingConfig(log_file_path=config.logfile_path, log_level=config.log_level).get_logger(
            self.__class__.__name__)

        # 回调函数（当检测到变化时调用）
        self.on_change_callback: Optional[Callable] = None

    @abstractmethod
    async def _init_get_hot_component(self) -> Any:
        """
        初始化获取热榜组件（由子类实现）

        Returns:
            平台特定的 GetHot 组件实例
        """
        pass

    @abstractmethod
    async def _navigate_to_hot_page(self) -> None:
        """
        导航到热榜页面（由子类实现）

        子类需要在此方法中：
        1. 跳转到平台热榜页面
        2. 等待页面加载完成
        3. 执行必要的页面交互
        """
        pass

    async def init(self):
        """
        初始化监控器（模板方法）

        流程：
        1. 验证页面
        2. 初始化 GetHot 组件
        3. 执行平台特定的初始化
        """
        try:
            if not self.page:
                raise ValueError("page 必须在使用前初始化")

            # 初始化获取热榜组件
            self._get_hot_component = await self._init_get_hot_component()

            # 执行额外的初始化逻辑（钩子方法）
            await self._post_init()

            self.log.info(f"{self.__class__.__name__} 初始化成功")

        except Exception as e:
            self.log.error(f"监控器初始化失败：{e}", exc_info=True)
            raise

    async def _post_init(self):
        """
        初始化后的钩子方法（可选重写）

        子类可以重写此方法执行额外的初始化逻辑
        """
        pass

    async def run_monitor(self, check_interval: int = 600, hot_titles_file: str = None):
        """
        启动监控循环（模板方法）

        :param check_interval: 检测间隔（秒）
        :param hot_titles_file: 热榜标题保存文件路径
        """
        try:
            if not self.page:
                self.log.error("页面未初始化")
                return

            if hot_titles_file is None:
                hot_titles_file = self.hot_titles_file

            count = 0
            while True:
                count += 1
                self.log.info(f"第 {count} 次检测")

                # 步骤1：持久化热榜标题
                await self._save_hot_title(hot_titles_file=hot_titles_file)

                # 步骤2：检查热榜变化
                await self._check_hot_titles_change()

                # 步骤3：等待下次检测
                await asyncio.sleep(check_interval)

        except Exception as e:
            self.log.error(f"监控器运行出错：{e}")
            raise

    async def _check_hot_titles_change(self):
        """
        检查热榜标题变化（模板方法）

        流程：
        1. 获取最新热榜数据
        2. 对比变化
        3. 触发回调
        """
        try:
            # 获取最新热榜数据
            hot_titles = await self._fetch_hot_titles()

            if not hot_titles:
                self.log.warning("未获取到热榜数据，跳过检查")
                return

            # 检查变化并触发回调
            await self._compare_and_notify(hot_titles)

        except Exception as e:
            self.log.error(f"检查热榜变化失败：{e}", exc_info=True)

    async def _fetch_hot_titles(self) -> List[dict]:
        """
        获取热榜数据（根据范围自动选择策略）

        Returns:
            热榜数据列表
        """
        if self.start_index and self.end_index:
            # 范围模式
            return await self._get_hot_component.get_hot_title_list(
                self.start_index,
                self.end_index
            )
        else:
            # 单个模式
            return await self._get_hot_component.get_hot_title_list(
                self.start_index,
                self.start_index
            )

    async def _compare_and_notify(self, new_hot_titles: List[dict]):
        """
        对比热榜变化并通知（模板方法）

        :param new_hot_titles: 新的热榜数据列表
        """
        if not self.hot_titles:
            # 首次运行，初始化历史数据
            self.hot_titles = [item['title'] for item in new_hot_titles]
            self.log.info(f"初始化热榜数据，共 {len(self.hot_titles)} 条")
            return

        new_titles = [item['title'] for item in new_hot_titles]

        # 边界检查
        max_index = min(len(new_titles), len(self.hot_titles))

        changed_count = 0
        for index in range(max_index):
            if new_titles[index] != self.hot_titles[index]:
                old_title = self.hot_titles[index]
                new_title = new_titles[index]

                self.log.info(
                    f"检测到榜单 {self.start_index + index} 发生变化："
                    f"{old_title} → {new_title}"
                )

                # 更新历史数据
                self.hot_titles[index] = new_title
                changed_count += 1

                # 触发回调（异步非阻塞）
                if self.on_change_callback:
                    task = asyncio.create_task(
                        self.on_change_callback(new_hot_titles[index])
                    )
                    self.log.debug(f"已创建任务处理变化：{new_title}")

        if changed_count == 0:
            self.log.debug("本次检测未发现变化")
        else:
            self.log.info(f"本次检测共发现 {changed_count} 个变化")

    async def _save_hot_title(self, hot_titles_file: str):
        """持久化保存热榜标题（通用实现）"""
        try:
            # 如果没有历史数据且文件存在，读取历史数据
            if not self.hot_titles and os.path.exists(hot_titles_file):
                with open(hot_titles_file, "r", encoding="utf-8") as f:
                    self.hot_titles = json.load(f)

                # 根据监控范围裁剪数据
                self._trim_hot_titles_by_range()

            # 如果没有历史数据且文件不存在，创建空文件
            elif not self.hot_titles:
                self.hot_titles = []
                os.makedirs(os.path.dirname(hot_titles_file), exist_ok=True)
                with open(hot_titles_file, "w", encoding="utf-8") as f:
                    json.dump([], f, ensure_ascii=False, indent=4)

            # 保存热榜标题到文件
            if self.hot_titles:
                os.makedirs(os.path.dirname(hot_titles_file), exist_ok=True)
                with open(hot_titles_file, 'w', encoding='utf-8') as f:
                    json.dump(self.hot_titles, f, ensure_ascii=False, indent=4)
                self.log.info(f"保存热榜标题成功，共 {len(self.hot_titles)} 个标题")

        except Exception as e:
            self.log.error(f"读取/保存热榜标题文件失败：{e}", exc_info=True)

    def _trim_hot_titles_by_range(self):
        """根据监控范围裁剪热榜数据"""
        if not self.hot_titles:
            return

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

    def set_monitor_range(self, start_index: int, end_index: Optional[int] = None):
        """
        设置监控范围

        :param start_index: 起始索引（从 1 开始）
        :param end_index: 结束索引（可选，不传则只监控单个）
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

    async def get_hot_list(self, start_index: int, end_index: int) -> list:
        """
        获取热榜数据（通用实现）

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

            hot_titles = await self._get_hot_component.get_hot_title_list(
                start_index,
                end_index
            )
            return hot_titles

        except Exception as e:
            self.log.error(f"获取热榜失败：{e}", exc_info=True)
            return []

    async def random_sleep(self, min_seconds: float = 1.0, max_seconds: float = 3.0) -> None:
        """随机延迟（模拟真人操作）"""
        import random
        delay = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(delay)
        self.log.debug(f"延迟 {delay:.2f}秒")
