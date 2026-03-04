from io import BytesIO
from PIL import Image
import time

from playwright.sync_api import Page, Locator, TimeoutError as PlaywrightTimeoutError
from app.tools.ElementWaiter import ElementWaiter
from app.core.config_manager import config
from app.tools.LoggingConfig import LoggingConfig


class Login:
    def __init__(self, page: Page):
        """初始化登录类"""
        self.page = page
        self.url = 'https://www.zhihu.com/signin?next=%2F'
        self.waiter = ElementWaiter(page=page)
        self.log = LoggingConfig(log_file_path=config.logfile_path).get_logger("Login")
        self.login_in = False
        self.image = None
        self.page.goto(self.url)

    def run(self):
        """启动登录流程：显示菜单 -> 获取选择 -> 执行登录方式"""
        if self.__is_already_logged_in():
            print("已经登录成功")
            self.log.info("已经登录成功")
            return

        self.__show_menu()
        choice = self.__get_user_choice()
        if choice == 0:
            print("退出程序")
            self.log.info("退出程序")
            return

        self.__execute_login(choice)

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

    def __execute_login(self, choice):
        """根据用户选择执行相应的登录方式"""
        if choice == 1:
            self.__login_by_qrcode()
        elif choice == 2:
            username = input("请输入用户名：")
            username = "13939826475"
            password = input("请输入密码：")
            password = "@@3085678256Gzj."

            self.__login_by_username_and_password(username=username, password=password)
        else:
            print("请输入正确的选择")
            self.log.info("请输入正确的选择")

    def __is_already_logged_in(self):
        """检查是否已登录"""
        return self.page.url != self.url

    def __login_by_username_and_password(self, username, password):
        """账号密码登录"""
        try:
            # 切换到密码登录 tab
            self.waiter.safe_click(selector='//div[@class="SignFlow-tab" and @role="button"]', selector_type="xpath")
            self.log.info("正在使用账号密码登录...")

            # 输入用户名和密码
            username_input = self.waiter.wait_for_element('input[name="username"]', selector_type="css")
            password_input = self.waiter.wait_for_element('input[name="password"]', selector_type="css")

            # 清空
            self.waiter.clear_input_field('input[name="username"]', selector_type="css")
            self.waiter.clear_input_field('input[name="password"]', selector_type="css")

            username_input.fill(username)
            password_input.fill(password)
            self.log.info("账号密码已输入")

            # 提交登录
            self.waiter.safe_click('//button[contains(@class, "SignFlow-submitButton")]')

            if self.waiter.wait_for_url_change(self.url, timeout=60000):
                print("登录成功")
                self.log.info("登录成功")
            else:
                print("登录失败：超时未跳转")
                self.log.error("登录失败：超时未跳转")

        except Exception as e:
            print(f"账号密码登录失败：{e}")
            self.log.error(f"账号密码登录失败：{e}")

    def __login_by_qrcode(self):
        """扫码登录：获取二维码并提示用户扫描"""
        try:
            qr_code_element = self.waiter.wait_for_element('.Qrcode-qrcode', selector_type="css")
            qr_image = self.__capture_qr_code(qr_code_element)
            self.image = qr_image
            self.__show_qr_code()
            print("请打开手机应用扫描二维码登录")

            if self.waiter.wait_for_url_change(self.url, timeout=60000):
                self.log.info("登录成功")
            else:
                self.log.error("登录失败：超时未跳转")

        except Exception as e:
            self.log.error(f"二维码登录失败：{e}")

    def __capture_qr_code(self, element: Locator):
        """
        截取指定元素的截图
        :param element: 二维码元素 (Locator)
        :return: 截图对象 (Image)
        """
        try:
            # 获取元素的边界框
            box = element.bounding_box()

            # 截取整个页面
            screenshot = self.page.screenshot()

            # 使用 PIL 裁剪出二维码区域
            from PIL import Image
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


if __name__ == '__main__':
    from app.core.PlaywrightDriver import PlaywrightDriver

    USER_DATA_DIR = r"D:\pythonproject\Ai_Blogger\driver\playwright_data"
    playwright_driver = PlaywrightDriver(user_data_dir=USER_DATA_DIR)
    context, page = playwright_driver.launch_browser(viewport_type="pc")

    login = Login(page=page)
    login.run()

    context.close()
