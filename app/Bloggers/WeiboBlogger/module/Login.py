from io import BytesIO
from PIL import Image
import asyncio
import re

from playwright.async_api import Page, Locator, TimeoutError as PlaywrightTimeoutError
from app.Bloggers.BaseLogin import BaseLogin
from app.tools.ElementWaiter import AsyncElementWaiter


class AsyncWeiboLogin(BaseLogin):
    def __init__(self, page: Page, user_data_dir: str):
        """初始化异步登录类"""
        super().__init__(page, user_data_dir)
        self.url = "https://passport.weibo.com/sso/signin"
        self.waiter = AsyncElementWaiter(page=page)
        self.login_in = False
        self.image = None

    async def login(self):
        """启动登录流程"""
        await self.page.goto(self.url)
        if await self.__is_already_logged_in():
            self.log.info("已经登录成功")
            return

        self._show_menu()
        choice = self.__get_user_choice()
        if choice == 0:
            print("退出程序")
            self.log.info("退出程序")
            return

        await self.__execute_login(choice)

    def _show_menu(self):
        """显示登录方式菜单"""
        print("欢迎使用 微博 Logger")
        print("1. 扫码登录")
        print("2. 账号密码登录")
        print("0. 退出程序")

    def __get_user_choice(self):
        """获取用户输入的选项"""
        try:
            choice = int(input("请输入你的选择："))
            return choice
        except ValueError:
            print("输入无效，请输入数字 0、1 或 2。")
            self.log.error("输入无效，请输入数字 0、1 或 2。")
            return -1

    async def __execute_login(self, choice):
        """根据用户选择执行相应的登录方式"""
        if choice == 1:
            await self._login_by_qrcode()
        elif choice == 2:
            # TODO 注意账号密码
            username = input("请输入用户名：")
            username = "13939826475"
            password = input("请输入密码：")
            password = "@@3085678256Gzj."

            await self._login_by_username_and_password(username=username, password=password)
        else:
            print("请输入正确的选择")
            self.log.info("请输入正确的选择")

    async def __is_already_logged_in(self):
        """检查是否已登录"""
        return self.page.url != self.url

    async def _login_by_username_and_password(self, username: str = None, password: str = None):
        """账号密码登录"""
        try:
            # 切换到账号密码登录
            await self.waiter.safe_click_locator(
                self.page.get_by_role("link", name="账号登录")
            )

            # 填充用户名
            username_field = self.page.get_by_placeholder("手机号或邮箱")
            await self.waiter.safe_fill_locator(username_field, username)

            # 填充密码
            password_field = self.page.get_by_placeholder("密码")

            await self.waiter.safe_fill_locator(password_field, password)

            self.log.info("账号密码已输入")

            # 点击登录按钮
            login_button = self.page.get_by_role("button", name="登录")

            await self.waiter.safe_click_locator(login_button)

            if await self.waiter.wait_for_url_change(self.url, timeout=60000):
                print("登录成功")
                self.log.info("登录成功")

                # 登录成功后立即保存 storage state
                try:
                    # 获取页面的上下文
                    context = self.page.context
                    # 构建 storage state 文件路径
                    import os
                    storage_state_file = os.path.join(
                        fr"{self.user_data_dir}",
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
        """扫码登陆"""
        try:
            qr_locator = self.page.locator("div").filter(
                has_text=re.compile(r"^扫描二维码登录打开微博手机APP - 我的页面 - 扫一扫$")).locator(
                "img")

            await self.waiter.wait_for_locator(qr_locator, condition="visible", timeout=10000)
            qr_image = await self.__capture_qr_code(qr_locator)
            self.image = qr_image
            self.__show_qr_code()
            self.log.info("请打开手机应用扫描二维码登录")

            if await self.waiter.wait_for_url_change(self.url, timeout=60000):
                print("登录成功")
                self.log.info("登录成功")

                # 登录成功后立即保存 storage state
                try:
                    # 获取页面的上下文
                    context = self.page.context
                    # 构建 storage state 文件路径
                    import os
                    storage_state_file = os.path.join(
                        fr"{self.user_data_dir}",
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
            self.log.error(f"二维码码登录失败：{e}")

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


async def test_weibo_login():
    from app.core.PlaywrightDriver import AsyncPlaywrightDriver

    USER_DATA_DIR = r"/driver/playwright_data"

    async with AsyncPlaywrightDriver(base_data_dir=USER_DATA_DIR) as driver:
        browser, context, _ = await driver.launch_browser(viewport_type="pc")
        page = await context.new_page()

        login = AsyncWeiboLogin(page=page, user_data_dir=f"{USER_DATA_DIR}/weibo_data")
        await login.login()


if __name__ == '__main__':
    asyncio.run(test_weibo_login())
