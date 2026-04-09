from playwright.async_api import BrowserContext
from typing import Any

from app.Bloggers.BaseMonitor import BaseMonitor


class ZhihuMonitor(BaseMonitor):
    """知乎热榜监控器 - 专注于知乎平台的监控逻辑"""

    def __init__(self, context: BrowserContext):
        """
        初始化监控器

        Args:
            context: Playwright BrowserContext 实例
        """
        super().__init__(platform_name="zhihu", context=context)

    async def _init_get_hot_component(self) -> Any:
        """初始化知乎热榜获取组件"""
        from app.Bloggers.ZhihuBlogger.scraping.GetHot import AsyncZhihuGetHot
        return AsyncZhihuGetHot(page=self.page)

    async def _navigate_to_hot_page(self) -> None:
        """导航到知乎热榜页面"""
        url = "https://www.zhihu.com/hot"
        self.log.info(f"🌐 正在导航到知乎热榜页面...")
        await self.page.goto(url, wait_until="domcontentloaded")
        await self.random_sleep(2, 4)

    async def _post_init(self):
        """初始化后导航到热榜页面"""
        await self._navigate_to_hot_page()
