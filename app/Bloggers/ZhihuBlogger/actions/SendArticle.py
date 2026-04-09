import asyncio
from typing import Optional, List, Tuple, Any
import asyncio
from playwright.async_api import Page, Locator
from app.core.config_manager import config
from app.Bloggers.BaseSendEssay import BaseSendEssay


class AsyncZhihuSendArticle(BaseSendEssay):
    def __init__(self, page: Page):
        """
        知乎发布文章机器人

        :param page: 知乎页面对象
        """
        super().__init__(platform_name="zhihu", page=page)

        self.update = False

    async def send_essay(self, data: dict[str, Any]):
        """
        发送文章

        流程：
            1. 进入 https://zhuanlan.zhihu.com/write
            2. 输入标题
            3. 导入正文（md)
            4. 添加封面 - 可选
            5. 点击“发布”按钮

        """
        try:
            # 文章标题
            title = data["title"]
            # 要上传的 Markdown 文件路径
            md_path = data["md_path"]
            # 要上传的封面图片路径 - 可选
            image_path = data.get("image_path", None)

            # 1. 进入 https://zhuanlan.zhihu.com/write
            self.url = config.platforms["zhihu"]["urls"].get("write")
            await self.page.goto(self.url)
            await self.__run(title, md_path, image_path)
            return True
        except Exception as e:
            self.log.error(f"发布文章失败：{e}")
            return False

    async def __run(self, title: str, md_path: str, image_path: str = None):
        """
        执行完整的发布文章流程

        Args:
            title: 文章标题
            md_path: 要上传的 Markdown 文件路径
            image_path: 要上传的封面图片路径 - 可选
        """
        try:
            await asyncio.sleep(5)  # 等待页面加载完成

            # 2. 输入标题
            await self.waiter.safe_click_locator(
                self.page.get_by_placeholder("请输入标题（最多 100 个字）")
            )

            await self.waiter.safe_fill_locator(
                self.page.get_by_placeholder("请输入标题（最多 100 个字）"), title
            )

            # 3. 导入正文（md）
            await self.waiter.safe_click_locator(
                self.page.get_by_label("导入")
            )
            await self.waiter.safe_click_locator(
                self.page.get_by_text("导入文档")
            )
            await asyncio.sleep(1)
            # 等待文件上传输入框出现
            upload_input = await self.waiter.wait_for_element(
                """//input[@type='file' and @accept='.docx,.markdown,.mdown,.mkdn,.md']""", condition="attached"
            )
            self.log.info("✅ 找到隐藏的 file input 元素")
            await upload_input.set_input_files(md_path)
            self.log.info(f"✅ 文件上传成功：{image_path}")

            await asyncio.sleep(5)

            # 4. 添加封面 - 可选
            if image_path:
                image_input = await self.waiter.wait_for_element(
                    """//input[@type='file' and @class='UploadPicture-input']""",
                    condition="attached",
                    timeout=self.element_timeout
                )
                await image_input.set_input_files(image_path)
                self.log.info(f"✅ 图片上传成功：{image_path}")
                await asyncio.sleep(10)  # 等待图片上传完成

            # 5.  点击“发布”按钮
            await self.waiter.safe_click_locator(
                self.page.get_by_role("button", name="发布")
            )
            await asyncio.sleep(2)
            self.log.info("✅ 文章已发布")
            return True
        except Exception as e:
            self.log.error(f"发布文章失败：{e}")
            return False


if __name__ == '__main__':
    async def test_zhihu_send_article():
        from app.core.PlaywrightDriver import AsyncPlaywrightDriver

        BASE_DATA_DIR = r"D:\pythonproject\Ai_Blogger\driver\playwright_data"

        async with AsyncPlaywrightDriver(base_data_dir=BASE_DATA_DIR) as driver:
            await driver.launch_browser()

            content = await driver.create_platform_context(
                platform_name="zhihu",
                user_data_dir=f"{BASE_DATA_DIR}/zhihu_data",
            )

            page = await content.new_page()

            send_article = AsyncZhihuSendArticle(page)
            await send_article.send_essay(title="测试标题", md_path="test.md",
                                          image_path="cf7726c7-5f12-45be-844d-758287c84f54-1.png")


    asyncio.run(test_zhihu_send_article())
