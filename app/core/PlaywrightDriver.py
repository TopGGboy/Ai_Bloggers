from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError
from typing import Optional, Tuple, Literal
import time
import random
import asyncio

from app.tools.LoggingConfig import LoggingConfig
from app.core.config_manager import config

REAL_UA_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
]


class AsyncPlaywrightDriver:
    """
    异步 Playwright 浏览器驱动类
    """

    def __init__(self, user_data_dir: Optional[str] = None, is_mobile: bool = False):
        """
        初始化异步 Playwright 驱动实例。

        :param user_data_dir: 浏览器用户数据目录路径，用于持久化会话（如 cookies、缓存等）
        :param is_mobile: 是否模拟移动设备，影响视口和用户代理等
        """
        self._playwright = None
        # 浏览器实例对象，类型为 playwright.async_api.Browser
        self._browser: Optional[Browser] = None
        # 浏览器上下文列表，每个上下文可视为独立的会话环境
        self._contexts: List[BrowserContext] = []
        # 页面对象列表，用于管理所有打开的标签页
        self._pages: List[Page] = []

        self.user_data_dir = user_data_dir
        self.debugger_address = "127.0.0.1:9222"
        self.is_mobile = is_mobile
        # 随机选择的真实用户代理字符串，用于模拟不同浏览器/设备
        self.user_agent = random.choice(REAL_UA_LIST)
        self.click_delay_range = (50, 200)
        self.type_delay_range = (50, 150)

        self.log = LoggingConfig(log_file_path=config.logfile_path).get_logger("AsyncPlaywrightDriver")

    async def launch_browser(self, viewport_type: Literal["pc", "mobile"] = "pc") -> Tuple[
        Browser, BrowserContext, Page]:
        """
        异步启动 Playwright 浏览器实例，并创建浏览器上下文和页面。

        该方法根据传入的视图类型（PC 或移动端）配置浏览器视口，并自动应用反检测脚本、
        路由拦截（屏蔽分析类请求）等增强功能。支持两种启动模式：
        - 持久化模式：如果指定了 `user_data_dir`，则使用 `launch_persistent_context` 启动，
          保留用户数据（如 Cookie、缓存）。
        - 临时模式：否则正常启动浏览器，再新建独立上下文。

        :param viewport_type: 视图类型，可选 'pc' 或 'mobile'，决定默认视口尺寸
                              - 'pc'   : 1920x1080
                              - 'mobile': 375x812
        :return: 包含三个元素的元组：
                 - browser    : Playwright 浏览器实例 (Browser)
                 - context    : 浏览器上下文实例 (BrowserContext)，用于管理多个页面
                 - page       : 新创建的标签页实例 (Page)
        :raises PlaywrightTimeoutError: 浏览器启动超时
        :raises Exception: 其他启动过程中的异常（如 Playwright 启动失败、上下文创建失败等）
        """
        try:
            self._playwright = await async_playwright().start()
            self.log.info("Playwright 异步启动成功")

            # 浏览器启动参数（用于 stealth 增强、性能优化、禁用自动化特征等）
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--start-maximized",
                "--disable-webgl",
                "--disable-extensions",
                "--disable-features=VizDisplayCompositor",
                "--lang=zh-CN",
                '--search-provider="name=百度;keyword=baidu;search_url=https://www.baidu.com/s?wd={searchTerms}"',
                '--disable-search-suggest',
            ]
            launch_kwargs = {
                "args": launch_args,
                "slow_mo": random.randint(100, 300),  # 操作延迟，模拟人类速度
                "headless": False,  # 是否无头模式（这里设为有头）
            }

            # 根据视图类型设置视口尺寸
            viewport_config = {"width": 1920, "height": 1080} if viewport_type == "pc" else {"width": 375,
                                                                                             "height": 812}
            context_kwargs = {
                "viewport": viewport_config,
                "user_agent": self.user_agent,
                "bypass_csp": True,  # 绕过内容安全策略
                "locale": "zh-CN",
                "timezone_id": "Asia/Shanghai",
                "geolocation": {"latitude": 31.2304, "longitude": 121.4737},  # 设置上海地理位置
                "permissions": ["geolocation"],  # 授予地理位置权限
            }

            if self.user_data_dir:
                # 启动持久化上下文（包含浏览器实例和上下文合一）
                self._browser = await self._playwright.chromium.launch_persistent_context(
                    user_data_dir=self.user_data_dir,
                    **context_kwargs,
                    **launch_kwargs,
                )
                self._contexts.append(self._browser)  # 对于持久化启动，browser 即上下文
                self.log.info(f"✅ 启动带持久化数据的浏览器：{self.user_data_dir}")
            else:
                # 启动普通浏览器，再创建新的上下文
                self._browser = await self._playwright.chromium.launch(**launch_kwargs)
                context = await self._browser.new_context(**context_kwargs)
                self._contexts.append(context)
                self.log.info("✅ 启动普通临时浏览器")

            # 加载反检测脚本（隐藏自动化特征）
            await self._load_anti_detection_script()

            # 在新创建的上下文中新建一个页面
            page = await self._contexts[-1].new_page()

            # 设置路由拦截：屏蔽常见的统计/追踪域名，其余正常继续
            await page.route("**/*", lambda route: route.continue_() if not route.request.url.startswith(
                ("https://analytics.", "https://track.")) else route.abort())

            self._pages.append(page)

            return self._browser, self._contexts[-1], page

        except PlaywrightTimeoutError as e:
            self.log.error(f"浏览器启动超时：{str(e)}")
            await self.quit()
            raise
        except Exception as e:
            self.log.error(f"浏览器启动失败：{str(e)}", exc_info=False)
            await self.quit()
            raise

    async def create_platform_context(self, platform_name: str,
                                      user_data_dir: str,
                                      viewport_type: Literal["pc", "mobile"] = "pc",
                                      custom_ua: Optional[str] = None) -> BrowserContext:
        """
        为特定平台创建独立的浏览器上下文（BrowserContext）。

        该方法在已启动的浏览器实例（`self._browser`）上，为不同的平台（如知乎、小红书）创建
        独立的上下文环境。每个上下文拥有独立的存储（cookies、缓存等）和配置（视口、用户代理、时区等），
        并可加载反检测脚本以避免自动化特征被识别。

        **使用前提：** 必须先通过 `launch_browser` 启动浏览器实例，否则 `self._browser` 为 None 会引发异常。

        :param platform_name: 平台名称，仅用于日志标识，如 "zhihu"、"xiaohongshu"
        :param user_data_dir: 该平台的数据持久化目录路径，用于保存 cookies 和本地存储等
                              （注意：当前实现仅为日志记录，并未实际使用该目录创建持久化上下文，
                              如需真正使用持久化，可改用 `browser.new_context` 的 `user_data_dir` 参数，
                              或使用 `launch_persistent_context`。此处仅为占位或未来扩展。）
        :param viewport_type: 视口类型，'pc'（1920x1080）或 'mobile'（375x812）
        :param custom_ua: 自定义用户代理字符串，若不提供则从 `REAL_UA_LIST` 中随机选取
        :return: 新创建的独立浏览器上下文实例（BrowserContext）
        :raises Exception: 如果创建上下文失败（如浏览器未启动、参数错误等），将记录错误并抛出异常
        """
        try:
            viewport_config = {"width": 1920, "height": 1080} if viewport_type == "pc" else {"width": 375,
                                                                                             "height": 812}
            context_kwargs = {
                "viewport": viewport_config,
                "user_agent": custom_ua or random.choice(REAL_UA_LIST),
                "bypass_csp": True,  # 绕过内容安全策略
                "locale": "zh-CN",
                "timezone_id": "Asia/Shanghai",
                "geolocation": {"latitude": 31.2304, "longitude": 121.4737},  # 上海坐标
                "permissions": ["geolocation"],  # 授予地理位置权限
            }

            # 为每个平台创建独立 Context
            context = await self._browser.new_context(**context_kwargs)
            # 为此上下文加载反检测脚本（如隐藏 webdriver 特征）
            await self._load_anti_detection_script_for_context(context)

            self._contexts.append(context)
            self.log.info(f"✅ 为 {platform_name} 创建独立 Context: {user_data_dir}")

            return context

        except Exception as e:
            self.log.error(f"创建 {platform_name} 平台的 Context 失败：{str(e)}", exc_info=False)
            raise

    async def _load_anti_detection_script(self):
        """
        为当前所有 Context 加载反检测脚本
        """
        anti_detection_code = """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh']});
            HTMLCanvasElement.prototype.toDataURL = function() { 
                return 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQImWNgYGBgAAAABQABh6FO1AAAAABJRU5ErkJggg=='; 
            };
            Object.defineProperty(navigator, 'mediaDevices', {get: () => ({getUserMedia: () => Promise.reject()})});
            Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
            delete window.__playwright_devtools_background_page;
        """
        for context in self._contexts:
            await context.add_init_script(script=anti_detection_code)
        self.log.info("✅ 加载反检测脚本")

    async def _load_anti_detection_script_for_context(self, context: BrowserContext):
        """为指定 Context 加载反检测脚本"""
        anti_detection_code = """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh']});
            HTMLCanvasElement.prototype.toDataURL = function() { 
                return 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQImWNgYGBgAAAABQABh6FO1AAAAABJRU5ErkJggg=='; 
            };
            Object.defineProperty(navigator, 'mediaDevices', {get: () => ({getUserMedia: () => Promise.reject()})});
            Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
            delete window.__playwright_devtools_background_page;
        """
        await context.add_init_script(anti_detection_code)

    async def quit(self):
        try:
            for page in self._pages:
                await page.close()
            for context in self._contexts:
                await context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
            self.log.info("浏览器资源已释放")
        except Exception as e:
            self.log.warning(f"关闭浏览器异常：{str(e)}", exc_info=False)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.quit()
        if exc_val:
            self.log.error(f"程序执行异常：{exc_val}")
        return False


if __name__ == '__main__':
    USER_DATA_DIR = r"D:\pythonproject\Ai_Blogger\driver\playwright_data"


    async def test_async():
        try:
            async with AsyncPlaywrightDriver(user_data_dir=USER_DATA_DIR) as driver:
                browser, context, page = await driver.launch_browser(viewport_type="pc")
                await page.goto("https://www.zhihu.com")
                await asyncio.sleep(random.randint(3, 5))
                await page.mouse.wheel(0, random.randint(200, 500))

                await page.goto("https://www.zhihu.com/people/me")
                driver.log.info(f"✅ 登录后页面标题：{await page.title()}")
        except Exception as e:
            driver.log.error(f"执行失败：{e}", exc_info=False)


    asyncio.run(test_async())
