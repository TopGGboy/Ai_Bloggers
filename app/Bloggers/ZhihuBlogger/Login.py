from io import BytesIO
from PIL import Image
import asyncio

from playwright.async_api import Page, Locator, TimeoutError as PlaywrightTimeoutError
from app.tools.ElementWaiter import AsyncElementWaiter
from app.core.config_manager import config
from app.tools.LoggingConfig import LoggingConfig


class AsyncLogin:
    def __init__(self, page: Page):
        """初始化异步登录类"""
        self.page = page
        self.url = 'https://www.zhihu.com/signin?next=%2F'
        self.waiter = AsyncElementWaiter(page=page)
        self.log = LoggingConfig(log_file_path=config.logfile_path, log_level=config.log_level).get_logger(
            self.__class__.__name__)
        self.login_in = False
        self.image = None

    async def run(self):
        """启动登录流程"""
        await self.page.goto(self.url)
        if await self.__is_already_logged_in():
            self.log.info("已经登录成功")
            return

        self.__show_menu()
        choice = self.__get_user_choice()
        if choice == 0:
            print("退出程序")
            self.log.info("退出程序")
            return

        await self.__execute_login(choice)

    def __show_menu(self):
        """显示登录方式菜单"""
        print("欢迎使用 知乎 Logger")
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
            await self.__login_by_qrcode()
        elif choice == 2:
            # TODO 注意账号密码
            username = input("请输入用户名：")
            username = "13939826475"
            password = input("请输入密码：")
            password = "@@3085678256Gzj."

            await self.__login_by_username_and_password(username=username, password=password)
        else:
            print("请输入正确的选择")
            self.log.info("请输入正确的选择")

    async def __is_already_logged_in(self):
        """检查是否已登录"""
        return self.page.url != self.url

    async def __login_by_username_and_password(self, username, password):
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
                        r"D:\pythonproject\Ai_Blogger\driver\playwright_data\zhihu_data",
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

    async def __login_by_qrcode(self):
        """扫码登录"""
        try:
            qr_code_element = await self.waiter.wait_for_element('.Qrcode-qrcode', selector_type="css")
            qr_image = await self.__capture_qr_code(qr_code_element)
            self.image = qr_image
            self.__show_qr_code()
            print("请打开手机应用扫描二维码登录")

            if await self.waiter.wait_for_url_change(self.url, timeout=60000):
                self.log.info("登录成功")
            else:
                self.log.error("登录失败：超时未跳转")

        except Exception as e:
            self.log.error(f"二维码登录失败：{e}")

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
    from app.core.PlaywrightDriver import AsyncPlaywrightDriver

    USER_DATA_DIR = r"D:\pythonproject\Ai_Blogger\driver\playwright_data"

    async with AsyncPlaywrightDriver(user_data_dir=USER_DATA_DIR) as driver:
        browser, context, page = await driver.launch_browser(viewport_type="pc")

        login = AsyncLogin(page=page)
        await login.run()


if __name__ == '__main__':
    asyncio.run(test_zhihu_login())
