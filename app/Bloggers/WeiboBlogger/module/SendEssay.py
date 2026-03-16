from typing import Optional, List, Tuple
import asyncio
from playwright.async_api import Page, Locator
from app.tools.ElementWaiter import AsyncElementWaiter
from app.tools.LoggingConfig import LoggingConfig
from app.core.config_manager import config
from app.Bloggers.BaseSendEssay import BaseSendEssay


class AsyncWeiboSendEssay(BaseSendEssay):
    def __init__(self, page: Page):
        """
        异步版本：微博发文自动化

        :param page: Playwright Page 实例
        """
        super().__init__(page=page)
        self.url = r"https://card.weibo.com/article/v5/editor#/draft"
        self.waiter = AsyncElementWaiter(page=self.page)
        self.update = False

    async def send_essay(self, file_path: str = None, href: str = None):
        """发送微博"""
        try:

            await self.page.goto(self.url)

            # 0. 点击写文章(新建一个文章，避免编辑已有文章)
            await self.waiter.safe_click_locator(
                self.page.get_by_role("button", name="写文章")
            )

            await asyncio.sleep(10)  # 等待页面加载完成

            # 1. 点击 输入正文
            content = "ce"

            await self.waiter.safe_fill_locator(
                self.page.locator(".tiptap"), content
            )

            # 2. 输入标题
            title = ""
            await self.waiter.safe_fill_locator(
                self.page.get_by_placeholder("请输入标题"), title
            )

            # 3. 输入导语
            summary = ""
            await self.waiter.safe_fill_locator(
                self.page.get_by_placeholder("导语（选填）"), summary
            )

            # 4. 设置文章封面
            await self.waiter.safe_click_locator(self.page.get_by_text("+ 设置文章封面"))
            await asyncio.sleep(2)
            await self.waiter.safe_click_locator(self.page.get_by_text("图片库"))

            # 5. 直接通过隐藏的 input 上传图片（绕过文件选择器）
            upload_input = await self.waiter.wait_for_element(
                """//input[@type='file' and contains(@accept,'.jpg')]""",
                condition="attached",
                timeout=5000
            )

            image_path = r"/Md/92917c72e24c4702bee6558f288ef959.png"

            if upload_input:
                await upload_input.set_input_files(image_path)
                self.log.info(f"✅ 图片上传成功：{image_path}")
            else:
                # 备用方案
                await self.waiter.safe_click_locator(self.page.get_by_text("上传"))
                await asyncio.sleep(1)
                upload_input = await self.waiter.wait_for_element(
                    """//input[@type='file' and contains(@accept,'.jpg')]""",
                    condition="attached"
                )
                if upload_input:
                    await upload_input.set_input_files(image_path)

            await asyncio.sleep(10)  # 等待图片上传完成

            # 6. 选择图片
            await self.waiter.safe_click_locator(self.page.locator(".select-mask").first, timeout=5000)

            # 7. 点击下一步
            await self.waiter.safe_click_locator(
                self.page.get_by_role("dialog").get_by_role("button", name="下一步")
            )

            # 8. 点击确定 图片
            await self.waiter.safe_click_locator(self.page.get_by_role("button", name="确定"))

            # 9. 点击下一步
            await self.waiter.safe_click_locator(self.page.get_by_role("button", name="下一步"))

            # 10. 点击发布
            await self.waiter.safe_click_locator(self.page.get_by_role("button", name="发布"))
        except Exception as e:
            self.log.error(f"发送微博失败：{e}")

    async def __get_essay_content(self, file_path: str):
        """获取文档内容"""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return content


async def test_weibo_send_essay():
    from app.core.PlaywrightDriver import AsyncPlaywrightDriver

    BASE_DATA_DIR = r"/driver/playwright_data"

    async with AsyncPlaywrightDriver(base_data_dir=BASE_DATA_DIR) as driver:
        await driver.launch_browser(viewport_type="pc")

        content = await driver.create_platform_context(
            platform_name="weibo",
            user_data_dir=f"{BASE_DATA_DIR}/weibo_data",
        )

        page = await content.new_page()

        send_essay = AsyncWeiboSendEssay(page)
        await send_essay.send_essay()


if __name__ == '__main__':
    asyncio.run(test_weibo_send_essay())
