from selenium.webdriver.common.by import By
from io import BytesIO
from PIL import Image

from app.core import EdgeDriver
from app.tools import ElementWaiter


class Login:
    def __init__(self):
        self.edgedriver = EdgeDriver.EdgeDriver(edge_driver_path=r'../../../driver/edgedriver/msedgedriver.exe')
        self.driver = None
        self.url = r'https://www.zhihu.com/signin?next=%2Fhot'
        # 创建等待器
        self.waiter = None

    def init(self, login_type):
        if login_type == 1:
            self.driver = self.edgedriver.new_Edge()
            # 创建等待器
            self.waiter = ElementWaiter.ElementWaiter(driver=self.driver)
            self.driver.get(self.url)
        elif login_type == 2:
            self.driver = self.edgedriver.control_Edge()
            # 创建等待器
            self.waiter = ElementWaiter.ElementWaiter(driver=self.driver)
            self.driver.get(self.url)

    # 账号密码登录
    def login_by_username_and_password(self, username, password):
        try:
            # 输出现在的url
            print(f"当前url: {self.driver.current_url}")
            # 点击密码登录
            self.waiter.safe_click(By.XPATH, '//div[@class="SignFlow-tab" and @role="button"]')
            print("正在使用账号密码登录...")

            # 找到用户名输入框 并 输入用户名
            username_input = self.waiter.wait_for_element(By.NAME, "username")
            print("账号输入框已找到")
            password_input = self.waiter.wait_for_element(By.NAME, "password")
            print("密码输入框已找到")

            # 输入用户名 和 密码
            self.waiter.clear_input_field(By.NAME, "username")
            self.waiter.clear_input_field(By.NAME, "password")
            username_input.send_keys(username)
            password_input.send_keys(password)
            print("账号密码已输入")

            # 点击登录按钮
            self.waiter.safe_click(By.XPATH,
                                   '//button[@class="Button SignFlow-submitButton FEfUrdfMIKpQDJDqkjte Button--primary Button--blue epMJl0lFQuYbC7jrwr_o JmYzaky7MEPMFcJDLNMG"]')
            self.check_pass = True
        except Exception as e:
            print(f"账号密码登录失败: {e}")

    # 扫码登录
    def login_by_qrcode(self):
        try:
            # 等待二维码元素的出现
            qr_code_element = self.waiter.wait_for_element(By.CLASS_NAME, 'Qrcode-qrcode')

            # 截取二维码图片
            qr_code_image = self.capture_qr_code(qr_code_element)
            self.image = qr_code_image
        except Exception as e:
            print(f"二维码登录失败: {e}")

    def login_way(self, choice=1):
        if choice == 1:  # 扫码登录
            self.init(login_type=choice)
            print("扫码登录中")
            self.login_by_qrcode()
            self.show_qr_code()
            print("请打开手机应用扫描二维码登录")

            if login.waiter.wait_for_url_change(login.url, timeout=60):
                print("登录成功")
                return driver
            else:
                print("登录失败")

        elif choice == 2:  # 账号密码登录
            self.init(login_type=choice)
            # 输入账号密码
            username = input("请输入你的用户名：")
            username = "13939826475"
            password = input("请输入你的密码：")
            password = "@@3085678256Gzj."
            self.login_by_username_and_password(username=username, password=password)
        else:
            print("请输入正确的选择")

    def menu(self):
        print("欢迎使用 知乎Logger")
        print("1.扫码登录")
        print("2.账号密码登录")
        print("0.退出程序")

    def capture_qr_code(self, element):
        """
        截取二维码图片
        :param element: 二维码元素
        :return: 二维码图片
        """
        # 获取元素的截图
        screenshot = element.screenshot_as_png
        image = Image.open(BytesIO(screenshot))
        return image

    def show_qr_code(self):
        """
        显示二维码图片
        """
        try:
            self.image.show()
        except Exception as e:
            print(f"显示二维码图片失败: {e}")

    def run(self):
        while True:
            self.menu()
            choice = int(input("请输入你的选择："))
            if choice == 0:
                break
            self.login_way(choice=choice)


if __name__ == '__main__':
    login = Login()
    login.run()
