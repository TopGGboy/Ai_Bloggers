import time
import json
import os
import asyncio

from playwright.sync_api import Page
from playwright.async_api import BrowserContext
from typing import Dict, Any, Optional

from app.tools.LoggingConfig import LoggingConfig
from app.core.config_manager import config
from app.Bloggers.BasePlatform import BasePlatform


class ZhihuAsyncControl(BasePlatform):
    """异步版本的知乎平台控制器"""

    def __init__(self, context: BrowserContext, md_path: str):
        super().__init__(context, md_path)

        # 延迟初始化各组件 (需要page后才能创建)
        self.page: Optional[Page] = None
        self.Zhihu_Login = None
        self.Zhihu_GetHot = None
        self.Zhihu_SendEssay = None
        self.Zhihu_WriteText = None
        self.str_2_md = None

        # 状态配置
        self.url = "https://www.zhihu.com/hot"
        self.user_input = ""
        self.start_index: Optional[int] = 1
        self.end_index: Optional[int] = 1
        self.hot_titles: Optional[List] = None

        # 保存 markdown 文件的路径（从入参接收）
        self.md_path = md_path
        # 新增：重试配置（提高健壮性）
        self.retry_config = {
            "login": 3,  # 登录最多重试3次
            "publish": 2,  # 发布最多重试2次
            "get_hot": 2  # 获取热榜最多重试2次
        }

    async def init(self) -> None:
        """初始化平台（登录、加载主页等）"""
        try:
            # 创建新页面
            self.page = await self.context.new_page()

            # 初始化异步版本的组件
            from app.Bloggers.ZhihuBlogger.Login import AsyncLogin
            from app.Bloggers.ZhihuBlogger.GetHot import AsyncGetHot
            from app.Bloggers.ZhihuBlogger.SendEssay import AsyncSendEssay
            from app.Bloggers.ZhihuBlogger.WriteText import WriteZhihuText
            from app.tools.Str2Md import Str2Md

            self.Zhihu_Login = AsyncLogin(page=self.page)
            self.Zhihu_GetHot = AsyncGetHot(page=self.page, logging=True)
            self.Zhihu_SendEssay = AsyncSendEssay(page=self.page)
            self.Zhihu_WriteText = WriteZhihuText(model_name="deepseek-chat")
            self.str_2_md = Str2Md()

            # 执行登录
            await self.Zhihu_Login.run()

            self.log.info("知乎平台初始化成功")

        except Exception as e:
            self.log.error(f"知乎平台初始化失败：{e}", exc_info=True)
            raise

    async def publish_content(self, content: Dict[str, Any], url: str = None) -> bool:
        """
        发布内容到知乎

        :param url: 目标问题的链接
        :param content:  内容字典，包含 title, content, images 等
        :return:   bool: 发布是否成功
        """
        try:
            if not self.page:
                self.log.error("页面未初始化")
                return False

            # 从 content 中提取数据
            title = content.get('title', '')
            text_content = content.get('content', '')
            images = content.get('images', [])

            # 保存为 Markdown 文件
            sanitized_title = self._sanitize_filename(title)
            file_name = os.path.join(self.md_path, f"{sanitized_title}.md")
            self.str_2_md.save_2_md(text_content, file_name=file_name)

            await self.Zhihu_SendEssay.run(href=url, file_path=file_name)

            self.log.info(f"内容发布成功：{title}")
            return True

        except Exception as e:
            self.log.error(f"发布内容失败：{e}", exc_info=True)
            return False

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

    async def run_monitor(self) -> None:
        """监控热榜变化"""
        try:
            if not self.page:
                self.log.error("页面未初始化")
                return

            count = 0
            while True:
                count += 1
                self.log.info(f"第 {count} 次检测")

                # 导航到热榜页面
                await self.page.goto(self.url)
                await self.random_sleep(2, 4)

                # 持久化保存热榜标题
                await self._save_hot_title(
                    hot_titles_file=r"D:\pythonproject\Ai_Blogger\app\Bloggers\ZhihuBlogger\hot_titles.json"
                )

                # 检查热榜标题变化
                if self.start_index and self.end_index:
                    await self._check_hot_titles()
                else:
                    await self._check_hot_single_title()

                # 每隔 10 min 检测一次
                await asyncio.sleep(600)

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
                    await self._generate_and_publish(hot_titles[index])

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
            # 空值检查，避免对比None报错
            if self.hot_titles and self.hot_titles[0] != new_title:
                self.log.info(f"检测到榜单 {self.start_index} 发生变化：{self.hot_titles[0]} → {new_title}")
                self.hot_titles[0] = new_title
                await self._generate_and_publish(new_title_list[0])

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

    async def _generate_and_publish(self, hot_title: dict):
        """生成文案并保存为 Markdown，然后发布文章"""
        try:
            hot_text_content = await self.Zhihu_GetHot.get_hot_content(hot_title['href'])
            hot_text, _ = self.Zhihu_WriteText.write_hot_text(
                hot_title['title'],
                hot_text_content['content'],
                hot_text_content['question_head']
            )

            # 使用标题生成安全的文件名
            sanitized_title = self._sanitize_filename(hot_title['title'])
            file_name = os.path.join(self.md_path, f"{sanitized_title}.md")

            # 保存 Markdown 文件
            self.str_2_md.save_2_md(hot_text, file_name=file_name)
            self.log.info(f"文章已保存至：{file_name}")

            # 发布文章
            await self.Zhihu_SendEssay.run(hot_title['href'], file_name)

        except Exception as e:
            self.log.error(f"生成并发布失败：{e}", exc_info=True)

    def _sanitize_filename(self, title: str) -> str:
        """清理标题中的特殊字符，使其适合作为文件名"""
        invalid_chars = r'<>"|*?/\\:'
        sanitized = title
        for char in invalid_chars:
            sanitized = sanitized.replace(char, '_')

        sanitized = ' '.join(sanitized.split())

        max_length = 200
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]

        return sanitized

    async def close(self) -> None:
        """关闭平台资源-修复：完整清理 Page + Context"""
        if self.page:
            await self.page.close()
            self.log.info("知乎页面已关闭")

        # 修复8：调用父类 close 关闭 Context（若父类实现）
        await super().close()
        self.log.info(f"{self.platform_name} 所有资源已关闭")
