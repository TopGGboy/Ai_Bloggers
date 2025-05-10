from typing import Optional, List, Tuple

from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains  # 滚轮
from selenium.webdriver.common.keys import Keys  # 添加导入Keys的语句
import time

from app.tools.ElementWaiter import ElementWaiter
from app.bloggers.zhihu_blogger.UploadFiles import UploadFiles


class SendEssay:
    def __init__(self, driver):
        """
        初始化知乎回答机器人对象。

        :param driver: WebDriver 实例
        """
        self.driver = driver
        self.url = r'https://www.zhihu.com/hot'
        self.waiter = ElementWaiter(driver=self.driver)
        self.driver.get(self.url)
        self.update = False  # 标记是否为更新已有回答
        self.upload_files = UploadFiles()  # 文件上传工具实例

    def __to_hot_item(self, num):
        """
        导航到指定序号的热榜条目详情页面，并切换窗口。

        :param num: 热榜条目序号（从1开始）
        """
        try:
            # 点击标题元素
            self.waiter.safe_click(By.XPATH,
                                   f'//section[@class="HotItem"][{num}]//h2[@class="HotItem-title"]')
            # 获取所有窗口句柄
            window_handles = self.driver.window_handles
            print(f"当前网页的 URL: {self.driver.current_url}")
            # 切换到新窗口
            self.driver.switch_to.window(window_handles[-1])
            # 打印当前网页的 URL
            print(f"当前网页的 URL: {self.driver.current_url}")

            # 添加滚轮下滑操作
            actions = ActionChains(self.driver)
            actions.scroll_by_amount(0, 400).perform()  # 滚动500像素

        except Exception as e:
            print(f"进入回答页面失败: {e}")

    def __process_answer_state(self):
        """
        检查是否存在“查看我的回答”按钮，判断是新建还是编辑模式。
        """
        # 检查是否存在“查看我的回答”按钮 就是已经写过回答了
        view_answer_button = self.waiter.wait_for_element(By.XPATH,
                                                          '//a[@class="Button FEfUrdfMIKpQDJDqkjte Button--blue JmYzaky7MEPMFcJDLNMG"]',
                                                          condition="presence", timeout=3)
        if view_answer_button:
            # 点击“查看我的回答”按钮
            self.waiter.safe_click(By.XPATH,
                                   '//a[@class="Button FEfUrdfMIKpQDJDqkjte Button--blue JmYzaky7MEPMFcJDLNMG"]')

            time.sleep(1)
            # 添加滚轮下滑操作
            actions = ActionChains(self.driver)
            actions.scroll_by_amount(0, 400).perform()  # 滚动500像素

            # 检查是否存在“编辑我的回答”按钮
            self.waiter.safe_click(By.XPATH,
                                   '//button[@type="button" and contains(@class, "Button FEfUrdfMIKpQDJDqkjte Button--blue JmYzaky7MEPMFcJDLNMG") and contains(text(), "编辑回答")]')
            self.update = True
        else:
            # 点击写回答按钮
            self.waiter.safe_click(By.XPATH,
                                   '//button[@type="button" and contains(@class, "Button FEfUrdfMIKpQDJDqkjte Button--blue JmYzaky7MEPMFcJDLNMG")]')
            self.update = False

        # 写回答，并提交

    def __write_answer(self, file_path):
        """
        清空文本框、上传文档并提交或更新回答。

        :param file_path: 要上传的 Markdown 文件路径
        """
        try:
            # 定位到写回答文本框并写入文本
            answer_textbox = self.waiter.safe_click(By.XPATH,
                                                    '//div[@class="DraftEditor-editorContainer"]//div[@role="textbox"]')
            # 删除文本框中的所有文本
            actions = ActionChains(self.driver)
            actions.click(answer_textbox)  # 点击文本框以确保焦点在文本框内
            actions.key_down(Keys.CONTROL).send_keys('a').key_up(Keys.CONTROL).perform()  # 全选文本
            actions.send_keys(Keys.DELETE).perform()  # 删除选中的文本

            # 点击上传文件
            # 点击文档按钮
            self.waiter.safe_click(By.XPATH,
                                   """//button[@aria-label='文档' and @type='button' and contains(@class, 'Button ToolbarButton css-3tq0b4 FEfUrdfMIKpQDJDqkjte Button--plain fEPKGkUK5jyc4fUuT0QP')]""")
            # 点击文档导入按钮
            self.waiter.safe_click(By.XPATH,
                                   """//div[@class='Editable-docModal-container' and .//div[@class='Editable-docModal-uploader-text' and text()='选择要导入的文档']]""")

            # 等待2s
            time.sleep(3)

            # 进入文件管理上传文件
            self.upload_files.run(file_path)

            # 等待2s
            time.sleep(5)

            if not self.update:
                # 点击提交按钮
                self.waiter.safe_click(By.XPATH,
                                       '//button[@type="button" and contains(@class, "Button css-78nr5c FEfUrdfMIKpQDJDqkjte Button--primary Button--blue epMJl0lFQuYbC7jrwr_o JmYzaky7MEPMFcJDLNMG")]')
                print("回答已提交")
            else:
                # 点击修改按钮
                self.waiter.safe_click(By.XPATH,
                                       '//button[@type="button" and contains(@class, "Button css-78nr5c FEfUrdfMIKpQDJDqkjte Button--primary Button--blue epMJl0lFQuYbC7jrwr_o JmYzaky7MEPMFcJDLNMG") and contains(text(), "提交修改")]')
                print("回答已修改")

            # 等待2s
            time.sleep(2)
        except Exception as e:
            print(f"回答提交失败: {e}")

    def __go_main_page(self):
        """
        关闭除主页面外的所有窗口，并切换回主页面。
        """
        # 获取所有窗口句柄
        window_handles = self.driver.window_handles
        print(window_handles)

        main_window = window_handles[-2]

        # 关闭其他窗口
        for window in window_handles[len(window_handles) - 1:]:
            self.driver.switch_to.window(window)
            time.sleep(2)
            self.driver.close()

        time.sleep(2)

        self.driver.switch_to.window(main_window)
        print("已返回主页面并关闭其他页面")

    def run(self, num: int, file_path: str):
        """
        执行完整的回答流程：
        1. 进入指定热榜条目
        2. 处理回答状态（新建/编辑）
        3. 编辑并提交回答
        4. 返回主页面

        :param num: 热榜条目序号
        :param file_path: 要上传的 Markdown 文件路径
        """
        self.__to_hot_item(num)
        self.__process_answer_state()
        self.__write_answer(file_path=file_path)
        time.sleep(2)
        self.__go_main_page()


def test_zhihu_answer_bot():
    """
    单独运行测试用例：模拟自动回答流程
    """
    edgedriver = EdgeDriver(edge_driver_path=r'../../../driver/edgedriver/msedgedriver.exe')
    driver = edgedriver.control_Edge()
    sendessay = SendEssay(driver)
    sendessay.run(num=1, file_path=r'D:\pythonproject\Ai_Blogger\Md\example_1.md')
    driver.quit()


if __name__ == '__main__':
    from app.core.EdgeDriver import EdgeDriver

    test_zhihu_answer_bot()
