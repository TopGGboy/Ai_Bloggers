from io import BytesIO
from PIL import Image
import asyncio

from playwright.async_api import Page, Locator, TimeoutError as PlaywrightTimeoutError
from app.core.config_manager import config
from app.bloggers.base_login import BaseLogin


class AsyncZhihuLogin(BaseLogin):
    def __init__(self, page: Page, user_data_dir: str = None):
        """初始化异步登录类"""
        super().__init__(platform_name="zhihu", page=page, user_data_dir=user_data_dir)

        self.login_in = False
        self.image = None

    async def login(self):
        """启动登录流程"""
        await self.page.goto(self.url)
        if await self.__is_already_logged_in():
            self.log.info("已经登录成功")
            return

        await self.__execute_login()

    async def __execute_login(self):
        """执行登录操作"""
        if self.login_type == "username_and_password":
            await self._login_by_username_and_password(username=self.username, password=self.password)
        elif self.login_type == "qrcode":
            await self._login_by_qrcode()

    async def __is_already_logged_in(self):
        """检查是否已登录"""
        return self.page.url != self.url

    async def _login_by_username_and_password(self, username: str = None, password: str = None):
        """账号密码登录"""
        try:
            await self.waiter.safe_click(selector='//div[@class="SignFlow-tab" and @role="button"]',
                                         selector_type="xpath")
            self.log.info("正在使用账号密码登录...")

            username_input = await self.waiter.wait_for_element('input[name="username"]', selector_type="css")
            password_input = await self.waiter.wait_for_element('input[name="password"]', selector_type="css")

            await self.waiter.clear_input_field('input[name="username"]', selector_type="css")
            await self.waiter.clear_input_field('input[name="password"]', selector_type="css")

            await username_input.fill(username)
            await password_input.fill(password)
            self.log.info("账号密码已输入")

            await self.waiter.safe_click('//button[contains(@class, "SignFlow-submitButton")]')

            if await self.waiter.wait_for_url_change(self.url, timeout=self.login_timeout):
                print("登录成功")
                self.log.info("登录成功")

                # 登录成功后立即保存 storage state
                try:
                    # 获取页面的上下文
                    context = self.page.context
                    # 构建 storage state 文件路径
                    import os
                    storage_state_file = os.path.join(
                        rf"{self.user_data_dir}",
                        "storage_state.json"
                    )
                    # 保存 storage state
                    await context.storage_state(path=storage_state_file)
                    self.log.info(f"✅ 登录成功后保存 storage state 到：{storage_state_file}")
                except Exception as e:
                    self.log.warning(f"保存 storage state 失败：{str(e)}")
            else:
                print("登录失败：超时未跳转")
                self.log.error("登录失败：超时未跳转")

        except Exception as e:
            print(f"账号密码登录失败：{e}")
            self.log.error(f"账号密码登录失败：{e}")

    async def _login_by_qrcode(self):
        """扫码登录- 不提取二维码图片，用户自己扫描"""
        try:
            # 等待登录成功（URL 变化表示登录成功）
            self.log.info(f"⏳ 等待扫码登录 (超时时间：{self.login_timeout}ms)")
            if await self.waiter.wait_for_url_change(self.url, timeout=self.login_timeout):
                self.log.info("✅ 登录成功")
                print("✅ 登录成功！")

                # 登录成功后立即保存 storage state
                try:
                    context = self.page.context
                    import os
                    storage_state_file = os.path.join(
                        rf"{self.user_data_dir}",
                        "storage_state.json"
                    )
                    await context.storage_state(path=storage_state_file)
                    self.log.info(f"✅ 已保存登录状态到：{storage_state_file}")
                except Exception as e:
                    self.log.warning(f"⚠️ 保存 storage state 失败：{str(e)}")
            else:
                self.log.error("❌ 登录失败：超时未扫码")
                print("❌ 登录超时，请重新尝试")

        except Exception as e:
            self.log.error(f"❌ 二维码登录失败：{e}", exc_info=True)
            print(f"❌ 二维码登录失败：{e}")
            raise

    # async def _login_by_qrcode(self):
    #     """扫码登录"""
    #     try:
    #         qr_code_element = await self.waiter.wait_for_element('.Qrcode-qrcode', selector_type="css")
    #         qr_image = await self.__capture_qr_code(qr_code_element)
    #         self.image = qr_image
    #         self.__show_qr_code()
    #         print("请打开手机应用扫描二维码登录")
    #
    #         if await self.waiter.wait_for_url_change(self.url, timeout=self.login_timeout):
    #             self.log.info("登录成功")
    #         else:
    #             self.log.error("登录失败：超时未跳转")
    #
    #     except Exception as e:
    #         self.log.error(f"二维码登录失败：{e}")

    async def __capture_qr_code(self, element: Locator):
        """截取二维码"""
        try:
            box = await element.bounding_box()
            screenshot = await self.page.screenshot()

            img = Image.open(BytesIO(screenshot))
            qr_image = img.crop((
                box['x'],
                box['y'],
                box['x'] + box['width'],
                box['y'] + box['height']
            ))

            return qr_image
        except Exception as e:
            print(f"截取二维码失败：{e}")
            raise

    def __show_qr_code(self):
        """显示二维码图片"""
        try:
            self.image.show()
        except Exception as e:
            print(f"显示二维码图片失败：{e}")
            self.log.error(f"显示二维码图片失败：{e}")


async def test_zhihu_login():
    from app.core.playwright_driver import AsyncPlaywrightDriver

    USER_DATA_DIR = r"/driver/playwright_data"

    async with AsyncPlaywrightDriver(user_data_dir=USER_DATA_DIR) as driver:
        browser, context, page = await driver.launch_browser(viewport_type="pc")

        login = AsyncZhihuLogin(page=page)
        await login.login()


if __name__ == '__main__':
    asyncio.run(test_zhihu_login())
