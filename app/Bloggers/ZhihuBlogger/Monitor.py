from playwright.async_api import BrowserContext

from app.Bloggers.BaseMonitor import BaseMonitor


class ZhihuMonitor(BaseMonitor):
    """知乎热榜监控器 - 专注于监控热榜变化"""

    def __init__(self, context: BrowserContext):
        """
        初始化监控器

        Args:
            context: Playwright BrowserContext 实例
        """
        super().__init__(context)
        self.Zhihu_GetHot = None

    async def init(self) -> None:
        """初始化监控器（不创建新 page，使用已有的 page）"""
        try:
            if not self.page:
                self.log.error("页面未初始化")
                raise ValueError("page 必须在使用前初始化")

            # 初始化获取热榜组件
            from app.Bloggers.ZhihuBlogger.module.GetHot import AsyncZhihuGetHot
            self.Zhihu_GetHot = AsyncZhihuGetHot(page=self.page, logging=True)

            self.log.info("知乎监控器初始化成功")

        except Exception as e:
            self.log.error(f"知乎监控器初始化失败：{e}", exc_info=True)
            raise

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
