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

    def __init__(self, base_data_dir: Optional[str] = None, is_mobile: bool = False):
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
        # 存储每个上下文对应的 storage state 文件路径
        self._context_storage_paths: Dict[BrowserContext, str] = {}

        self.base_data_dir = base_data_dir
        self.debugger_address = "127.0.0.1:9222"
        self.is_mobile = is_mobile
        # 随机选择的真实用户代理字符串，用于模拟不同浏览器/设备
        self.user_agent = random.choice(REAL_UA_LIST)
        self.click_delay_range = (50, 200)
        self.type_delay_range = (50, 150)

        self.log = LoggingConfig(log_file_path=config.logfile_path, log_level=config.log_level).get_logger(
            self.__class__.__name__)

    async def launch_browser(self,
                             viewport_type: Literal["pc", "mobile"] = "pc",
                             user_data_dir: Optional[str] = None) -> Tuple[
        Browser, BrowserContext, Page]:
        """
        异步启动 Playwright 浏览器实例（支持持久化上下文）。

        如果提供了 user_data_dir，则使用 storage_state.json 实现持久化，
        包括 Cookie、LocalStorage 等会话状态的自动保存和恢复（与 create_platform_context 相同的机制）。

        如果没有提供，则使用普通模式（不带持久化），
        由各平台通过 create_platform_context 自行管理持久化。

        :param viewport_type: 视图类型，可选 'pc' 或 'mobile'
                              - 'pc'   : 1920x1080
                              - 'mobile': 375x812
        :param user_data_dir: 持久化数据目录（可选），提供后自动启用 storage_state 持久化
        :return: 包含三个元素的元组：
                 - browser    : Playwright 浏览器实例 (Browser)
                 - context    : 浏览器上下文实例 (BrowserContext)，持久化时会自动保存关闭
                 - page       : 新创建的标签页实例 (Page)
        :raises PlaywrightTimeoutError: 浏览器启动超时
        :raises Exception: 其他启动过程中的异常
        """
        try:
            from pathlib import Path
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

            # 启动浏览器
            self._browser = await self._playwright.chromium.launch(**launch_kwargs)

            # 确定是否使用持久化模式
            data_dir = user_data_dir or self.base_data_dir

            if data_dir:
                # ----- 持久化模式（与 create_platform_context 机制一致） -----
                data_path = Path(data_dir)
                data_path.mkdir(parents=True, exist_ok=True)
                storage_state_file = data_path / "storage_state.json"

                if storage_state_file.exists():
                    context_kwargs["storage_state"] = str(storage_state_file)
                    self.log.info(f"📂 加载持久化状态：{storage_state_file}")
                else:
                    self.log.info(f"🆕 创建新上下文（首次使用，无持久化状态）")

                context = await self._browser.new_context(**context_kwargs)
                self._context_storage_paths[context] = str(storage_state_file)
                self.log.info("✅ 启动持久化浏览器（storage_state 自动管理）")
            else:
                # ----- 普通模式（不带持久化） -----
                context = await self._browser.new_context(**context_kwargs)
                self.log.info("✅ 启动普通浏览器（持久化由各平台 Context 自己管理）")

            self._contexts.append(context)

            # 创建新页面并添加到页面列表（供 quit 时统一清理）
            page = await context.new_page()
            self._pages.append(page)

            # 加载反检测脚本
            await self._load_anti_detection_script()

            return self._browser, context, page

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
        为特定平台创建独立的持久化浏览器上下文（BrowserContext）。

        该方法在已启动的浏览器实例上，为不同平台创建独立的持久化上下文环境。
        每个上下文拥有：
        - 独立的 Cookie 存储
        - 独立的 LocalStorage/SessionStorage
        - 独立的缓存
        - 独立的登录状态

        **核心特性：** 使用 `storage_state` 实现持久化，而不是 `launch_persistent_context`

        :param platform_name: 平台名称，如 "zhihu"、"xiaohongshu"
        :param user_data_dir: 该平台的持久化数据目录（绝对路径）
        :param viewport_type: 视口类型，'pc' 或 'mobile'
        :param custom_ua: 自定义用户代理字符串
        :return: 新创建的持久化浏览器上下文实例
        :raises Exception: 如果创建上下文失败
        """
        try:
            # 确保平台数据目录存在
            from pathlib import Path
            platform_data_path = Path(user_data_dir)
            platform_data_path.mkdir(parents=True, exist_ok=True)

            # 定义 storage state 文件路径
            storage_state_file = platform_data_path / "storage_state.json"

            viewport_config = {"width": 1920, "height": 1080} if viewport_type == "pc" else {"width": 375,
                                                                                             "height": 812}
            context_kwargs = {
                "viewport": viewport_config,
                "user_agent": custom_ua or random.choice(REAL_UA_LIST),
                "bypass_csp": True,
                "locale": "zh-CN",
                "timezone_id": "Asia/Shanghai",
                "geolocation": {"latitude": 31.2304, "longitude": 121.4737},
                "permissions": ["geolocation"],
            }

            # 如果 storage state 文件存在，加载它以实现持久化
            if storage_state_file.exists():
                context_kwargs["storage_state"] = str(storage_state_file)
                self.log.info(f"📂 加载平台 {platform_name} 的持久化状态：{storage_state_file}")
            else:
                self.log.info(f"🆕 创建平台 {platform_name} 的新上下文（首次使用）")

            # 为此平台创建新的上下文
            context = await self._browser.new_context(**context_kwargs)

            # 保存 storage state 文件路径
            self._context_storage_paths[context] = str(storage_state_file)

            # 加载反检测脚本
            await self._load_anti_detection_script_for_context(context)

            self._contexts.append(context)

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
            self.log.info("开始关闭浏览器资源...")

            # 1. 先保存每个上下文的 storage state
            self.log.info(f"正在保存 {len(self._contexts)} 个上下文的 storage state...")
            save_tasks = []
            for i, context in enumerate(self._contexts):
                try:
                    storage_state_path = self._context_storage_paths.get(context)
                    if storage_state_path:
                        self.log.info(f"💾 保存上下文 {i} 的 storage state 到：{storage_state_path}")
                        save_tasks.append(context.storage_state(path=storage_state_path))
                    else:
                        self.log.warning(f"上下文 {i} 没有对应的 storage state 文件路径")
                except Exception as e:
                    self.log.warning(f"准备保存上下文 {i} 失败：{str(e)}")

            # 并发保存所有 storage state
            if save_tasks:
                try:
                    await asyncio.gather(*save_tasks, return_exceptions=True)
                    self.log.info("✅ 所有 storage state 已保存")
                except Exception as e:
                    self.log.warning(f"保存 storage state 异常：{str(e)}")

            # 2. 关闭所有页面（带超时）
            self.log.info(f"正在关闭 {len(self._pages)} 个页面...")
            for page in self._pages:
                try:
                    await asyncio.wait_for(page.close(), timeout=5.0)
                except Exception as e:
                    self.log.warning(f"关闭页面失败：{str(e)}")

            # 3. 关闭所有上下文（带超时）
            self.log.info(f"正在关闭 {len(self._contexts)} 个上下文...")
            for context in self._contexts:
                try:
                    await asyncio.wait_for(context.close(), timeout=5.0)
                except Exception as e:
                    self.log.warning(f"关闭上下文失败：{str(e)}")

            # 4. 关闭浏览器（带超时）
            if self._browser:
                self.log.info("正在关闭浏览器...")
                try:
                    await asyncio.wait_for(self._browser.close(), timeout=10.0)
                    self.log.info("✅ 浏览器已关闭")
                except Exception as e:
                    self.log.warning(f"关闭浏览器失败：{str(e)}")

            # 5. 停止 playwright（带超时）
            if self._playwright:
                self.log.info("正在停止 playwright...")
                try:
                    await asyncio.wait_for(self._playwright.stop(), timeout=5.0)
                    self.log.info("✅ playwright 已停止")
                except Exception as e:
                    self.log.warning(f"停止 playwright 失败：{str(e)}")

            # 6. 清理引用，帮助垃圾回收
            self._pages.clear()
            self._contexts.clear()
            self._context_storage_paths.clear()
            self._browser = None
            self._playwright = None

            self.log.info("✅ 所有浏览器资源已释放")
        except Exception as e:
            self.log.warning(f"关闭浏览器异常：{str(e)}", exc_info=True)

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
