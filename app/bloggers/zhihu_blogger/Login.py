from selenium.webdriver.common.by import By
from io import BytesIO
from PIL import Image

from app.tools.ElementWaiter import ElementWaiter


class Login:
    def __init__(self, driver):
        """初始化登录类"""
        self.driver = driver
        self.url = 'https://www.zhihu.com/signin?next=%2Fhot'
        self.waiter = ElementWaiter(driver=self.driver)  # 创建元素等待器
        self.login_in = False  # 登录状态
        self.image = None
        self.driver.get(self.url)

    def run(self):
        """启动登录流程：显示菜单 -> 获取选择 -> 执行登录方式"""
        self.__show_menu()
        choice = self.__get_user_choice()
        if choice == 0:
            print("退出程序")
            return
        self.__execute_login(choice)

    def __show_menu(self):
        """显示登录方式菜单"""
        print("欢迎使用 知乎Logger")
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
            return -1

    def __execute_login(self, choice):
        """根据用户选择执行相应的登录方式"""
        if self.__is_already_logged_in():
            print("已经登录成功")
            return

        if choice == 1:
            self.__login_by_qrcode()
        elif choice == 2:
            username = input("请输入用户名：")
            username = "13939826475"  # TODO 注意
            password = input("请输入密码：")
            password = "@@3085678256Gzj."  # TODO 注意

            self.__login_by_username_and_password(username=username, password=password)
        else:
            print("请输入正确的选择")

    def __is_already_logged_in(self):
        """检查是否已登录"""
        return self.driver.current_url != self.url

    def __login_by_username_and_password(self, username, password):
        """账号密码登录"""
        try:
            # 切换到密码登录 tab
            self.waiter.safe_click(By.XPATH, '//div[@class="SignFlow-tab" and @role="button"]')
            print("正在使用账号密码登录...")

            # 输入用户名和密码
            username_input = self.waiter.wait_for_element(By.NAME, "username")
            password_input = self.waiter.wait_for_element(By.NAME, "password")
            # 清空
            self.waiter.clear_input_field(By.NAME, "username")
            self.waiter.clear_input_field(By.NAME, "password")
            username_input.send_keys(username)
            password_input.send_keys(password)
            print("账号密码已输入")

            # 提交登录
            self.waiter.safe_click(By.XPATH,
                                   '//button[contains(@class, "SignFlow-submitButton")]')

            if self.waiter.wait_for_url_change(self.url, timeout=60):
                print("登录成功")
            else:
                print("登录失败：超时未跳转")

        except Exception as e:
            print(f"账号密码登录失败: {e}")

    def __login_by_qrcode(self):
        """扫码登录：获取二维码并提示用户扫描"""
        try:
            qr_code_element = self.waiter.wait_for_element(By.CLASS_NAME, 'Qrcode-qrcode')
            qr_image = self.__capture_qr_code(qr_code_element)
            self.image = qr_image
            self.__show_qr_code()
            print("请打开手机应用扫描二维码登录")

            if self.waiter.wait_for_url_change(self.url, timeout=60):
                print("登录成功")
            else:
                print("登录失败：超时未跳转")

        except Exception as e:
            print(f"二维码登录失败: {e}")

    def __capture_qr_code(self, element):
        """
        截取指定元素的截图
        :param element: 二维码元素
        :return: 截图对象 (Image)
        """
        screenshot = element.screenshot_as_png
        return Image.open(BytesIO(screenshot))

    def __show_qr_code(self):
        """显示二维码图片"""
        try:
            self.image.show()
        except Exception as e:
            print(f"显示二维码图片失败: {e}")


if __name__ == '__main__':
    from app.core.EdgeDriver import EdgeDriver

    edgedriver = EdgeDriver(edge_driver_path=r'../../../driver/edgedriver/msedgedriver.exe')
    driver = edgedriver.control_Edge()

    login = Login(driver=driver)
    login.run()

    driver.quit()
