import asyncio
from typing import Optional, List
from bs4 import BeautifulSoup
from playwright.async_api import Page
from app.core.config_manager import config
from app.bloggers.base_get_hot import BaseGetHot


class AsyncZhihuGetHot(BaseGetHot):
    def __init__(self, page: Page):
        """
        异步版本：获取知乎热榜信息

        :param page: Playwright Page 实例
        """
        super().__init__(platform_name="zhihu", page=page)

    async def get_hot_title_list(self, begin, end):
        """获取指定范围内的热榜标题"""
        try:
            await self.page.goto(self.url)
            await self.waiter.wait_for_element('div.HotList-list', selector_type="css")

            html_data = await self.page.content()
            result = self.__parse_hot_title_list(html_data)

            return result[begin - 1:end]
        except Exception as e:
            return []

    async def get_hot_content_list(self, href):
        """获取知乎热榜内容"""
        try:
            await self.page.goto(href)
            await self.waiter.wait_for_element('div.List-item', selector_type="css")

            await self.waiter.safe_click('//button[contains(text(),"显示全部")]')
            await asyncio.sleep(1)

            html_data = await self.page.content()
            result = self.__parse_hot_content(html_data)

            return result
        except Exception as e:
            return []

    def __parse_hot_title_list(self, hot_title_html):
        """解析知乎热榜标题列表页面"""
        soup = BeautifulSoup(hot_title_html, 'html.parser')

        hot_list_container = soup.find("div", class_="HotList-list")
        if not hot_list_container:
            return []

        hot_items = hot_list_container.find_all("section", class_="HotItem")

        result = []
        for index, item in enumerate(hot_items):
            title_elem = item.find("h2", class_="HotItem-title")
            title = title_elem.text.strip() if title_elem else ""

            link_elem = item.find("a", href=True)
            href = link_elem["href"] if link_elem else ""

            if href and not href.startswith("http"):
                href = "https://www.zhihu.com" + href

            result.append({
                "title": title,
                "href": href
            })

        return result

    def __parse_hot_content(self, hot_content_html):
        """解析知乎热榜内容页面"""
        soup = BeautifulSoup(hot_content_html, 'html.parser')

        list_container = soup.find("div", class_="css-0", role="list")
        hot_items = list_container.find_all("div", class_="List-item")

        hot_contents = []

        for item in hot_items:
            content_html = item.find("div", class_="RichContent-inner")
            hot_contents.append(content_html.text if content_html else "")

        question_head = None
        content_span = soup.find('span', class_='RichText ztext css-10o75c2')

        if content_span:
            question_head = content_span.text

        result = {
            "question_head": question_head,
            "content": hot_contents
        }

        return result


async def test_zhihu_hot_fetcher():
    from app.core.playwright_driver import AsyncPlaywrightDriver

    USER_DATA_DIR = r"/driver/playwright_data"

    async with AsyncPlaywrightDriver(user_data_dir=USER_DATA_DIR) as driver:
        browser, context, page = await driver.launch_browser(viewport_type="pc")

        get_hot = AsyncZhihuGetHot(page, logging=True)

        """
        思路：
        1. 获取热榜标题以及热榜链接 
        {
            "title": "标题",
            "link": "链接"
        }
        2. 如果变化则，则开始获取相关信息
        3. 获取热榜信息
        {
            "title": "标题",
            "link": "链接",
            "content": "内容"
        }
        4. ai 生成文案
        """
        hot_title_lists = await get_hot.get_hot_title_list(1, 1)
        print(hot_title_lists)
        print(hot_title_lists[0]["href"])
        hot_content = await get_hot.get_hot_content_list(hot_title_lists[0]["href"])
        print(hot_content)


if __name__ == '__main__':
    asyncio.run(test_zhihu_hot_fetcher())
