from typing import Any

from playwright.async_api import BrowserContext

from app.Bloggers.BaseMonitor import BaseMonitor


class WeiboMonitor(BaseMonitor):
    """微博监控器 - 专注于监微博变化"""

    def __init__(self, context: BrowserContext):
        """
        初始化监控器

        :param context: Playwright BrowserContext 实例
        """
        super().__init__(platform_name="weibo", context=context)

    async def _init_get_hot_component(self) -> Any:
        """初始化微博热榜获取组件"""
        from app.Bloggers.WeiboBlogger.scraping.GetHot import AsyncWeiboGetHot
        return AsyncWeiboGetHot(page=self.page)

    async def _navigate_to_hot_page(self) -> None:
        """导航到微博热榜页面"""
        self.log.info(f"🌐 正在导航到微博热榜页面...")
        await self.page.goto(self.hot_url, wait_until="domcontentloaded")
        await self.random_sleep(2, 4)
