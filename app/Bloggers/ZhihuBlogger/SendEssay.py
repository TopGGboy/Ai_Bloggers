from typing import Optional, List, Tuple
import time
import os
from playwright.sync_api import Page, Locator
from app.tools.ElementWaiter import ElementWaiter
from app.tools.LoggingConfig import LoggingConfig
from app.Bloggers.ZhihuBlogger.UploadFiles import UploadFiles
from app.core.config_manager import config


class SendEssay:
    def __init__(self, page: Page):
        """
        初始化知乎回答机器人对象。

        :param page: Playwright Page 实例
        """
        self.page = page
        self.url = r'https://www.zhihu.com/hot'
        self.waiter = ElementWaiter(page=self.page)
        self.log = LoggingConfig(log_file_path=config.logfile_path).get_logger("SendEssay")
        self.page.goto(self.url)
        self.update = False
        self.upload_files = UploadFiles()

    def __to_hot_item(self, href):
        """
        导航到指定热榜条目的详情页面

        :param href: 热榜条目链接
        """
        try:
            # 直接跳转到指定链接
            self.page.goto(href)

            # 打印当前网页的 URL
            self.log.info(f"当前网页的 URL: {self.page.url}")

            # # 添加滚轮下滑操作
            # self.page.mouse.wheel(0, 400)
            # time.sleep(0.5)

        except Exception as e:
            print(f"进入回答页面失败：{e}")
            self.log.error(f"进入回答页面失败：{e}")

    def __process_answer_state(self):
        """
        检查是否存在"查看我的回答"按钮，判断是新建还是编辑模式。
        """
        # 检查是否存在"查看我的回答"按钮
        view_answer_button = self.waiter.wait_for_element(
            '//a[@class="Button FEfUrdfMIKpQDJDqkjte Button--blue JmYzaky7MEPMFcJDLNMG"]',
            condition="visible",
            timeout=3000
        )

        change_answer_button = self.waiter.wait_for_element(
            '//button[@type="button" and contains(@class, "Button FEfUrdfMIKpQDJDqkjte Button--blue JmYzaky7MEPMFcJDLNMG") and contains(text(), "编辑回答")]',
            condition="visible",
            timeout=3000
        )

        if view_answer_button:
            # 点击"查看我的回答"按钮
            self.waiter.safe_click('//a[@class="Button FEfUrdfMIKpQDJDqkjte Button--blue JmYzaky7MEPMFcJDLNMG"]')

            time.sleep(1)
            # 滚动
            self.page.mouse.wheel(0, 400)
            time.sleep(0.5)

            # 检查并点击"编辑回答"按钮
            self.waiter.safe_click(
                '//button[@type="button" and contains(@class, "Button FEfUrdfMIKpQDJDqkjte Button--blue JmYzaky7MEPMFcJDLNMG") and contains(text(), "编辑回答")]')
            self.update = True
        elif change_answer_button:
            # 检查并点击"编辑回答"按钮
            self.waiter.safe_click(
                '//button[@type="button" and contains(@class, "Button FEfUrdfMIKpQDJDqkjte Button--blue JmYzaky7MEPMFcJDLNMG") and contains(text(), "编辑回答")]')
        else:
            # 点击写回答按钮
            self.waiter.safe_click(
                '//button[@type="button" and contains(@class, "Button FEfUrdfMIKpQDJDqkjte Button--blue JmYzaky7MEPMFcJDLNMG")]')
            self.update = False

        # 点击写回答按钮

        self.waiter.safe_click("""//main//button[contains(text(), '写回答') and @type='button']""")

        self.update = False

    def __write_answer(self, file_path):
        """
        清空文本框、上传文档并提交或更新回答。

        :param file_path: 要上传的 Markdown 文件路径
        """
        try:
            # 删除文本框中的所有文本
            # 先聚焦到文本框
            textbox_locator = self.page.locator('//div[@class="DraftEditor-editorContainer"]//div[@role="textbox"]')
            textbox_locator.click()

            # 全选并删除
            self.page.keyboard.press('Control+a')
            self.page.keyboard.press('Delete')

            # 点击导入
            self.waiter.safe_click("""//div[@class='css-dvxtzn']/span[@class='css-8atqhb' and text()='导入']/../..""")

            time.sleep(1)

            # 点击导入文档
            self.waiter.safe_click("""//button[@aria-label='导入文档' and contains(text(),'导入文档')]""")

            time.sleep(1)

            upload_input = self.waiter.wait_for_element(
                """//input[@type='file' and @accept='.docx,.markdown,.mdown,.mkdn,.md']""", condition="attached"
            )
            self.log.info("✅ 找到隐藏的 file input 元素")

            # 原生上传（即使 input 隐藏，set_input_files 仍可生效）
            upload_input.set_input_files(file_path)
            self.log.info(f"✅ 文件上传成功：{file_path}")

            # 等待
            time.sleep(5)

            if not self.update:
                # 点击提交按钮
                self.waiter.safe_click(
                    '//button[@type="button" and contains(@class, "Button css-78nr5c FEfUrdfMIKpQDJDqkjte Button--primary Button--blue epMJl0lFQuYbC7jrwr_o JmYzaky7MEPMFcJDLNMG")]')
                print("回答已提交")
                self.log.info("回答已提交")
            else:
                # 点击修改按钮
                self.waiter.safe_click(
                    '//button[@type="button" and contains(@class, "Button css-78nr5c FEfUrdfMIKpQDJDqkjte Button--primary Button--blue epMJl0lFQuYbC7jrwr_o JmYzaky7MEPMFcJDLNMG") and contains(text(), "提交修改")]')
                print("回答已修改")
                self.log.info("回答已修改")

            # 等待
            time.sleep(2)
        except Exception as e:
            print(f"回答提交失败：{e}")
            self.log.error(f"回答提交失败：{e}")

    def __go_main_page(self):
        """
        关闭除主页面外的所有窗口，并切换回主页面。
        """
        # Playwright 中管理多个页面的方式不同
        # 如果需要可以后续实现
        pass

    def run(self, href: str, file_path: str):
        """
        执行完整的回答流程：
        1. 进入指定热榜条目
        2. 处理回答状态（新建/编辑）
        3. 编辑并提交回答
        4. 返回主页面

        :param href: 热榜条目链接
        :param file_path: 要上传的 Markdown 文件路径
        """
        self.__to_hot_item(href)

        self.__process_answer_state()
        self.__write_answer(file_path=file_path)
        time.sleep(2)


def test_zhihu_answer_bot():
    """
    单独运行测试用例：模拟自动回答流程
    """
    from app.core.PlaywrightDriver import PlaywrightDriver
    USER_DATA_DIR = r"D:\pythonproject\Ai_Blogger\driver\playwright_data"
    playwright_driver = PlaywrightDriver(user_data_dir=USER_DATA_DIR)
    context, page = playwright_driver.launch_browser(viewport_type="pc")

    sendessay = SendEssay(page)
    sendessay.run(href="https://www.zhihu.com/question/2011788981294081499",
                  file_path=r"D:\pythonproject\Ai_Blogger\Md\example_1.md")
    context.close()


if __name__ == '__main__':
    from app.core.EdgeDriver import EdgeDriver

    test_zhihu_answer_bot()
