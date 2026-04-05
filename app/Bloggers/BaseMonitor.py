import asyncio
import json
import os
from abc import ABC
from playwright.async_api import BrowserContext, Page
from typing import Any, Optional, List, Callable

from app.tools.LoggingConfig import LoggingConfig
from app.core.config_manager import config


class BaseMonitor(ABC):
    """
    监控器基类 - 定义所有监控器的统一接口
    """

    def __init__(self, platform_name: str, context: BrowserContext):
        """
        初始化监控器

        :param context: Playwright 的浏览器上下文，用于创建新页面
        """
        self.context = context
        self.page: Optional[Page] = None
        self.start_index: Optional[int] = 1
        self.end_index: Optional[int] = 1
        self.hot_titles: Optional[List] = None

        # 日志
        self.log = LoggingConfig(log_file_path=config.logfile_path, log_level=config.log_level).get_logger(
            self.__class__.__name__)

        self.hot_titles_file = config.platforms[platform_name]["paths"]["hot_title_file"]

        # 回调函数（当检测到变化时调用）
        self.on_change_callback: Optional[Callable] = None

    async def init(self):
        """初始化监控器(不创建新 page，使用已有的 page)"""
        pass

    async def run_monitor(self, check_interval: int = 600, hot_titles_file: str = None, Get_Hot_Class=None):
        """
        启动监控循环

        :param check_interval: 检测间隔（秒），默认 600 秒
        :param hot_titles_file: 热榜标题保存文件路径
        :param Get_Hot_Class: 获取热榜的类
        :return:
        """
        try:
            if not self.page:
                self.log.error("页面未初始化")
                return

            if hot_titles_file is None:
                hot_titles_file = rf"./{self.__class__.__name__}_hot_titles.json"

            count = 0
            while True:
                count += 1
                self.log.info(f"第 {count} 次检测")

                # 持久化热榜标题
                await self._save_hot_title(hot_titles_file=hot_titles_file)

                # 检查热榜标题变化
                if self.start_index and self.end_index:
                    await self._check_hot_titles(Get_Hot_Class=Get_Hot_Class)
                else:
                    await self._check_hot_single_title(Get_Hot_Class=Get_Hot_Class)

                # 每隔指定时间检测一次
                await asyncio.sleep(check_interval)

        except Exception as e:
            self.log.error(f"监控器 {self.__class__.__name__} 运行出错：{e}")
            raise

    async def _check_hot_titles(self, Get_Hot_Class: Any = None):
        """
        检查热榜标题变化

        :param Get_Hot_Class:  获取热榜的类
        :return:
        """
        try:
            hot_titles = await Get_Hot_Class.get_hot_title_list(self.start_index, self.end_index)
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

    async def _check_hot_single_title(self, Get_Hot_Class: Any = None):
        """
        检查单个热榜标题变化

        :param Get_Hot_Class:  获取热榜的类
        :return:
        """
        try:
            new_title_list = await Get_Hot_Class.get_hot_title_list(self.start_index, self.start_index)
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

    async def random_sleep(self, min_seconds: float = 1.0, max_seconds: float = 3.0) -> None:
        """随机延迟（模拟真人操作）"""
        import random
        delay = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(delay)
        self.log.debug(f"延迟 {delay:.2f}秒")
