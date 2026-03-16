from typing import Optional, List, Tuple
import asyncio
from playwright.async_api import Page, Locator
from app.tools.ElementWaiter import AsyncElementWaiter
from app.tools.LoggingConfig import LoggingConfig
from app.core.config_manager import config
from app.Bloggers.BaseSendEssay import BaseSendEssay


class AsyncZhihuSendEssay(BaseSendEssay):
    def __init__(self, page: Page):
        """
        异步版本：知乎回答机器人

        :param page: Playwright Page 实例
        """
        super().__init__(page=page)
        self.url = r'https://www.zhihu.com/hot'
        self.waiter = AsyncElementWaiter(page=self.page)
        self.update = False

    async def __to_hot_item(self, href):
        """导航到指定热榜条目的详情页面"""
        try:
            await self.page.goto(href)
            self.log.info(f"当前网页的 URL: {self.page.url}")
        except Exception as e:
            print(f"进入回答页面失败：{e}")
            self.log.error(f"进入回答页面失败：{e}")

    async def __process_answer_state(self):
        """检查是否存在"查看我的回答"按钮"""
        view_answer_button = await self.waiter.wait_for_element(
            '//a[@class="Button FEfUrdfMIKpQDJDqkjte Button--blue JmYzaky7MEPMFcJDLNMG"]',
            condition="visible",
            timeout=3000
        )

        change_answer_button = await self.waiter.wait_for_element(
            '//button[@type="button" and contains(@class, "Button FEfUrdfMIKpQDJDqkjte Button--blue JmYzaky7MEPMFcJDLNMG") and contains(text(), "编辑回答")]',
            condition="visible",
            timeout=3000
        )

        if view_answer_button:
            await self.waiter.safe_click('//a[@class="Button FEfUrdfMIKpQDJDqkjte Button--blue JmYzaky7MEPMFcJDLNMG"]')
            await asyncio.sleep(1)
            await self.page.mouse.wheel(0, 400)
            await asyncio.sleep(0.5)

            await self.waiter.safe_click(
                '//button[@type="button" and contains(@class, "Button FEfUrdfMIKpQDJDqkjte Button--blue JmYzaky7MEPMFcJDLNMG") and contains(text(), "编辑回答")]')
            self.update = True
        elif change_answer_button:
            await self.waiter.safe_click(
                '//button[@type="button" and contains(@class, "Button FEfUrdfMIKpQDJDqkjte Button--blue JmYzaky7MEPMFcJDLNMG") and contains(text(), "编辑回答")]')
        else:
            await self.waiter.safe_click(
                '//button[@type="button" and contains(@class, "Button FEfUrdfMIKpQDJDqkjte Button--blue JmYzaky7MEPMFcJDLNMG")]')
            self.update = False

        await self.waiter.safe_click("""//main//button[contains(text(), '写回答') and @type='button']""")
        self.update = False

    async def __write_answer(self, file_path):
        """清空文本框、上传文档并提交或更新回答"""
        try:
            textbox_locator = self.page.locator('//div[@class="DraftEditor-editorContainer"]//div[@role="textbox"]')
            await textbox_locator.click()

            await self.page.keyboard.press('Control+a')
            await self.page.keyboard.press('Delete')

            await self.waiter.safe_click(
                """//div[@class='css-dvxtzn']/span[@class='css-8atqhb' and text()='导入']/../..""")
            await asyncio.sleep(1)

            await self.waiter.safe_click("""//button[@aria-label='导入文档' and contains(text(),'导入文档')]""")
            await asyncio.sleep(1)

            upload_input = await self.waiter.wait_for_element(
                """//input[@type='file' and @accept='.docx,.markdown,.mdown,.mkdn,.md']""", condition="attached"
            )
            self.log.info("✅ 找到隐藏的 file input 元素")

            await upload_input.set_input_files(file_path)
            self.log.info(f"✅ 文件上传成功：{file_path}")

            await asyncio.sleep(5)

            if not self.update:
                await self.waiter.safe_click(
                    '//button[@type="button" and contains(@class, "Button css-78nr5c FEfUrdfMIKpQDJDqkjte Button--primary Button--blue epMJl0lFQuYbC7jrwr_o JmYzaky7MEPMFcJDLNMG")]')
                print("回答已提交")
                self.log.info("回答已提交")
            else:
                await self.waiter.safe_click(
                    '//button[@type="button" and contains(@class, "Button css-78nr5c FEfUrdfMIKpQDJDqkjte Button--primary Button--blue epMJl0lFQuYbC7jrwr_o JmYzaky7MEPMFcJDLNMG") and contains(text(), "提交修改")]')
                print("回答已修改")
                self.log.info("回答已修改")

            await asyncio.sleep(2)
        except Exception as e:
            print(f"回答提交失败：{e}")
            self.log.error(f"回答提交失败：{e}")

    async def send_essay(self, href: str, file_path: str):
        """
        执行完整的回答流程：
        1. 进入指定热榜条目
        2. 处理回答状态（新建/编辑）
        3. 编辑并提交回答
        4. 返回主页面

        :param href: 热榜条目链接
        :param file_path: 要上传的 Markdown 文件路径
        """
        await self.__to_hot_item(href)

        await self.__process_answer_state()
        await self.__write_answer(file_path=file_path)
        await asyncio.sleep(2)


async def test_zhihu_answer_bot():
    """
    单独运行测试用例：模拟自动回答流程
    """
    from app.core.PlaywrightDriver import AsyncPlaywrightDriver

    USER_DATA_DIR = r"D:\pythonproject\Ai_Blogger\driver\playwright_data"

    async with AsyncPlaywrightDriver(user_data_dir=USER_DATA_DIR) as driver:
        browser, context, page = await driver.launch_browser(viewport_type="pc")

        sendessay = AsyncSendEssay(page)
        await sendessay.send_essay(href="https://www.zhihu.com/question/2011788981294081499",
                                   file_path=r"D:\pythonproject\Ai_Blogger\Md\example_1.md")


if __name__ == '__main__':
    asyncio.run(test_zhihu_answer_bot())
