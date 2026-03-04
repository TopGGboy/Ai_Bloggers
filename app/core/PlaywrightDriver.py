from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError
from typing import Optional, Tuple, Literal
import time
import random

from app.tools.LoggingConfig import LoggingConfig
from app.core.config_manager import config

REAL_UA_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
]


class PlaywrightDriver:
    def __init__(self, user_data_dir: Optional[str] = None, is_mobile: bool = False):
        self._playwright: Optional[sync_playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

        self.user_data_dir = user_data_dir
        self.debugger_address = "127.0.0.1:9222"
        self.is_mobile = is_mobile
        self.user_agent = random.choice(REAL_UA_LIST)
        self.click_delay_range = (50, 200)
        self.type_delay_range = (50, 150)

        self.log = LoggingConfig(log_file_path=config.logfile_path).get_logger("PlaywrightDriver")

    def launch_browser(self, viewport_type: Literal["pc", "mobile"] = "pc") -> Tuple[BrowserContext, Page]:
        """
        修复核心：
        1. 拆分参数：把 args/slow_mo/headless 从 context_kwargs 移到 launch_kwargs
        2. new_context() 只传它支持的参数
        """
        try:
            self._playwright = sync_playwright().start()
            self.log.info("Playwright 启动成功")

            # 1. 浏览器启动参数（仅传给 launch / launch_persistent_context）
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--start-maximized",
                "--disable-webgl",
                "--disable-extensions",
                "--disable-features=VizDisplayCompositor",
                "--lang=zh-CN",
                # 设置默认搜索引擎为百度
                '--search-provider="name=百度;keyword=baidu;search_url=https://www.baidu.com/s?wd={searchTerms}"',
                # 禁用 Google 搜索建议
                '--disable-search-suggest',
            ]
            launch_kwargs = {
                "args": launch_args,
                "slow_mo": random.randint(100, 300),
                "headless": False,  # 必须关闭无头模式
            }

            # 2. 上下文配置参数（传给 new_context / launch_persistent_context）
            viewport_config = {"width": 1920, "height": 1080} if viewport_type == "pc" else {"width": 375,
                                                                                             "height": 812}
            context_kwargs = {
                "viewport": viewport_config,
                "user_agent": self.user_agent,
                "bypass_csp": True,
                "locale": "zh-CN",
                "timezone_id": "Asia/Shanghai",
                "geolocation": {"latitude": 31.2304, "longitude": 121.4737},
                "permissions": ["geolocation"],
            }

            # ========== 分模式启动 ==========
            if self.user_data_dir:
                # 模式1：持久化登录态（知乎反风控核心）
                # launch_persistent_context 支持所有 launch + context 参数
                self._context = self._playwright.chromium.launch_persistent_context(
                    user_data_dir=self.user_data_dir,
                    **launch_kwargs,  # 传入启动参数
                    **context_kwargs  # 传入上下文参数
                )
                self._browser = self._context.browser
                self.log.info(f"✅ 启动带持久化数据的浏览器：{self.user_data_dir}")
            else:
                # 模式2：普通临时浏览器（无持久化）
                self._browser = self._playwright.chromium.launch(**launch_kwargs)  # 传入启动参数
                self._context = self._browser.new_context(**context_kwargs)  # 仅传入上下文参数
                self.log.info("✅ 启动普通临时浏览器")

            # 反检测脚本（保持不变）
            self._context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh']});
                HTMLCanvasElement.prototype.toDataURL = function() { 
                    return 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQImWNgYGBgAAAABQABh6FO1AAAAABJRU5ErkJggg=='; 
                };
                Object.defineProperty(navigator, 'mediaDevices', {get: () => ({getUserMedia: () => Promise.reject()})});
                Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
                delete window.__playwright_devtools_background_page;
            """)
            self.log.info("✅ 反检测脚本加载完成")

            # 创建页面
            self._page = self._context.new_page()
            # 拦截追踪请求（反风控）
            self._page.route("**/*", lambda route: route.continue_() if not route.request.url.startswith(
                ("https://analytics.", "https://track.")) else route.abort())

            return self._context, self._page

        except PlaywrightTimeoutError as e:
            self.log.error(f"浏览器启动超时：{str(e)}")
            self.quit()
            raise
        except Exception as e:
            self.log.error(f"浏览器启动失败：{str(e)}", exc_info=False)
            self.quit()
            raise

    # 以下方法完全保持不变
    def connect_existing_browser(self) -> Tuple[BrowserContext, Page]:
        try:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.connect_over_cdp(f"http://{self.debugger_address}")
            self.log.info(f"成功连接到调试浏览器：{self.debugger_address}")
            self._context = self._browser.contexts[0] if self._browser.contexts else self._browser.new_context()
            self._page = self._context.new_page()
            return self._context, self._page
        except Exception as e:
            self.log.error(f"连接已有浏览器失败：{str(e)}", exc_info=False)
            self.quit()
            raise

    def quit(self):
        try:
            if self._page:
                self._page.close()
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
            self.log.info("浏览器资源已释放")
        except Exception as e:
            self.log.warning(f"关闭浏览器异常：{str(e)}", exc_info=False)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.quit()
        if exc_val:
            self.log.error(f"程序执行异常：{exc_val}")
        return False

    @property
    def page(self) -> Page:
        if not self._page:
            raise ValueError("页面未初始化，请先调用launch_browser")
        return self._page

    @property
    def context(self) -> BrowserContext:
        if not self._context:
            raise ValueError("上下文未初始化，请先调用launch_browser")
        return self._context


# 测试示例（保持不变）
if __name__ == '__main__':
    USER_DATA_DIR = r"D:\pythonproject\Ai_Blogger\driver\playwright_data"
    try:
        with PlaywrightDriver(user_data_dir=USER_DATA_DIR) as driver:
            context, page = driver.launch_browser(viewport_type="pc")
            page.goto("https://www.zhihu.com")
            time.sleep(random.randint(3, 5))
            page.mouse.wheel(0, random.randint(200, 500))

            page.goto("https://www.zhihu.com/people/me")
            logger.info(f"✅ 登录后页面标题：{page.title()}")
    except Exception as e:
        logger.error(f"执行失败：{e}", exc_info=False)
