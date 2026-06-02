from typing import Optional, List, Tuple, Any
import asyncio
from playwright.async_api import Page, Locator
from app.core.config_manager import config
from app.bloggers.base_send_essay import BaseSendEssay


class AsyncWeiboSendEssay(BaseSendEssay):
    def __init__(self, page: Page):
        """
        异步版本：微博发文自动化

        :param page: Playwright Page 实例
        """
        super().__init__(platform_name="weibo", page=page)

        self.update = False

    async def send_essay(self, data: dict[str, Any]):
        """发送微博"""
        try:
            title = data["title"]
            content = data["content"]
            image_path = data["image_path"]
            summary = data.get("summary", None)

            await self.__run(title, content, image_path, summary)
        except Exception as e:
            self.log.error(f"发送微博失败：{e}")

    async def __run(self, title: str, content: str, image_path: str, summary: str = None):
        """运行微博发文流程"""
        try:
            await self.page.goto(self.url)

            # 0. 点击写文章(新建一个文章，避免编辑已有文章)
            await self.waiter.safe_click_locator(
                self.page.get_by_role("button", name="写文章")
            )

            await asyncio.sleep(10)  # 等待页面加载完成

            await self.waiter.safe_fill_locator(
                self.page.locator(".tiptap"), content
            )

            # 2. 输入标题
            await self.waiter.safe_fill_locator(
                self.page.get_by_placeholder("请输入标题"), title
            )

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
                timeout=self.element_timeout
            )

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
            await self.waiter.safe_click_locator(self.page.locator(".select-mask").first, timeout=self.element_timeout)

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
            self.log.info("✅ 微博发布成功")
            return True
        except Exception as e:
            self.log.error(f"微博微博失败：{e}")
            return False


async def test_weibo_send_essay():
    from app.core.playwright_driver import AsyncPlaywrightDriver

    BASE_DATA_DIR = r"/driver/playwright_data"

    async with AsyncPlaywrightDriver(base_data_dir=BASE_DATA_DIR) as driver:
        await driver.launch_browser(viewport_type="pc")

        content = await driver.create_platform_context(
            platform_name="weibo",
            user_data_dir=f"{BASE_DATA_DIR}/weibo_data",
        )

        page = await content.new_page()

        send_essay = AsyncWeiboSendEssay(page)
        await send_essay.send_essay(content={"title": "测试标题", "content": "测试内容", "summary": "测试摘要语"})


if __name__ == '__main__':
    asyncio.run(test_weibo_send_essay())
