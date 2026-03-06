from app.core.PlaywrightDriver import AsyncPlaywrightDriver
from app.Bloggers.ZhihuBlogger.Control import ZhihuAsyncControl
from app.tools.LoggingConfig import LoggingConfig
from app.core.config_manager import config
import asyncio


class MastControl:
    def __init__(self, md_path: str = None, playwright_driver_data: str = None):
        self.md_path = md_path or r'D:\pythonproject\Ai_Blogger\Md'
        self.playwright_driver_data = playwright_driver_data or r'D:\pythonproject\Ai_Blogger\driver\playwright_data'

        # 异步浏览器驱动
        self.driver = AsyncPlaywrightDriver(user_data_dir=self.playwright_driver_data)
        self.browser = None
        self.context = None

        # 平台字典
        self.platforms = {}

        # 日志配置
        self.log = LoggingConfig(log_file_path=config.logfile_path).get_logger(self.__class__.__name__)

    async def init(self):
        """初始化浏览器和所有平台"""
        try:
            # 启动浏览器
            self.browser, self.context, _ = await self.driver.launch_browser(viewport_type="pc")
            self.log.info("✅ 浏览器实例启动成功")

            # 创建并初始化知乎平台
            zhihu_platform = ZhihuAsyncControl(context=self.context, md_path=self.md_path)
            await zhihu_platform.init()
            self.platforms['zhihu'] = zhihu_platform

            self.log.info("✅ 知乎平台初始化完成")

        except Exception as e:
            self.log.error(f"初始化失败：{e}", exc_info=True)
            raise

    async def publish_content_concurrent(self, content: dict, url: str = None):
        """
        并发发布内容到所有平台

        Args:
            content: 内容字典
            url: 目标话题链接
        """
        if not self.platforms:
            self.log.warning("没有已注册的平台")
            return

        self.log.info(f"🚀 开始并发发布到 {len(self.platforms)} 个平台...")

        # 创建所有平台的发布任务
        tasks = {
            name: platform.publish_content(content, url=url)
            for name, platform in self.platforms.items()
        }

        # 并发执行
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        # 收集结果
        for (name, _), result in zip(tasks.items(), results):
            if isinstance(result, Exception):
                self.log.error(f"❌ 平台 {name} 发布失败：{result}")
            else:
                status = "✅" if result else "❌"
                self.log.info(f"{status} 平台 {name} 发布{'成功' if result else '失败'}")

    async def monitor_platform(self, platform_name: str, interval: int = 600):
        """
        监控单个平台的热榜变化

        Args:
            platform_name: 平台名称
            interval: 监控间隔（秒）
        """
        if platform_name not in self.platforms:
            self.log.error(f"平台 {platform_name} 未注册")
            return

        platform = self.platforms[platform_name]
        count = 0

        while True:
            count += 1
            self.log.info(f"[{platform_name}] 第 {count} 次检测")

            try:
                await platform.run_monitor()
            except Exception as e:
                self.log.error(f"[{platform_name}] 监控任务失败：{e}", exc_info=True)

            await asyncio.sleep(interval)

    async def monitor_all_platforms(self, intervals: dict = None):
        """
        并发监控所有平台

        Args:
            intervals: 各平台的监控间隔（秒）
            例如：{'zhihu': 600}
        """
        if intervals is None:
            intervals = {'zhihu': 600}

        tasks = [
            self.monitor_platform(name, interval)
            for name, interval in intervals.items()
            if name in self.platforms
        ]

        await asyncio.gather(*tasks)

    async def close_all(self):
        """关闭所有平台和浏览器"""
        self.log.info("正在关闭所有平台...")

        # 关闭所有平台
        for platform in self.platforms.values():
            await platform.close()

        # 关闭浏览器
        await self.driver.quit()

        self.log.info("✅ 所有资源已关闭")

    async def run(self, mode: str = "monitor"):
        """
        主运行入口

        Args:
            mode: 运行模式
                  - "monitor": 监控热榜变化
                  - "publish": 发布内容
        """
        self.log.info("=" * 40)
        self.log.info("       欢迎使用 Ai_Blogger (异步并发版)")
        self.log.info("=" * 40)

        try:
            # 初始化
            await self.init()

            if mode == "monitor":
                # 监控模式
                self.log.info("🔍 启动热榜监控模式...")
                await self.monitor_all_platforms(intervals={'zhihu': 600})

            elif mode == "publish":
                # 发布模式
                self.log.info("📝 启动内容发布模式...")
                test_content = {
                    'title': '测试标题',
                    'content': '这是测试内容',
                    'images': []
                }
                await self.publish_content_concurrent(test_content, url="https://www.zhihu.com/question/2012488083849889743")

            await self.close_all()

        except KeyboardInterrupt:
            self.log.info("用户中断程序")
            await self.close_all()
        except Exception as e:
            self.log.error(f"程序异常：{e}", exc_info=True)
            await self.close_all()
            raise