import asyncio
from typing import Optional, List
from bs4 import BeautifulSoup

from playwright.async_api import Page
from app.Bloggers.BaseGetHot import BaseGetHot


class AsyncWeiboGetHot(BaseGetHot):
    def __init__(self, page: Page):
        """
        获取微博热榜信息

        :param page: Playwright Page 实例
        """
        super().__init__(platform_name="weibo", page=page)

    async def get_hot_title_list(self, begin, end):
        """获取指定范围内的热榜标题"""
        try:
            await self.page.goto(self.url)
            await self.waiter.wait_for_element('div.vue-recycle-scroller__item-wrapper', selector_type="css")

            html_data = await self.page.content()
            result = self.__parse_hot_title_list(html_data)
            self.log.info(f"获取微博热榜标题成功")

            return result[begin - 1:end]
        except Exception as e:
            self.log.error(f"获取微博热榜标题失败：{e}")
            return []

    async def get_hot_content_list(self, href):
        """获取热榜内容"""
        try:
            await self.page.goto(href)
            await self.waiter.wait_for_element("div.card-wrap", selector_type="css")

            html_data = await self.page.content()
            result = self.__parse_hot_content_list(html_data)
            self.log.info(f"获取微博热榜内容成功")
            return result

        except Exception as e:
            self.log.error(f"获取微博热榜内容失败：{e}")
            return []

    def __parse_hot_content_list(self, hot_content_html):
        """解析微博热榜内容列表页面"""
        soup = BeautifulSoup(hot_content_html, 'html.parser')

        list_container = soup.find("div", id="pl_feedlist_index")
        if not list_container:
            self.log.error("未找到微博热榜内容列表容器")
            return []

        # 查找所有微博条目
        feed_items = list_container.find_all("div", attrs={"action-type": "feed_list_item"})

        hot_contents = []

        for item in feed_items:
            content_elem = item.find("p", attrs={"node-type": "feed_list_content"})
            hot_contents.append(content_elem.get_text(strip=True))

        result = {
            "question_head": None,
            "content": hot_contents
        }

        return result

    def __parse_hot_title_list(self, hot_title_html):
        """解析微博热榜标题列表页面"""
        soup = BeautifulSoup(hot_title_html, 'html.parser')

        hot_title_container = soup.find("div", class_="vue-recycle-scroller__item-wrapper")
        if not hot_title_container:
            return []

        hot_items = hot_title_container.find_all("div", class_="vue-recycle-scroller__item-view")

        result = []
        for index, item in enumerate(hot_items):
            if index == 0:
                continue

            # 查找标题链接元素
            title_elem = item.find("a", class_=lambda x: x and "tit_s5b56_65" in x)

            if title_elem:
                title = title_elem.get_text(strip=True)
                link = title_elem.get("href")

                # 如果链接是相对路径，转换为完整 URL
                if link and not link.startswith("http"):
                    link = f"https:{link}"

                if title:
                    result.append({
                        "title": title,
                        "href": link
                    })

        return result


async def test_weibo_hot_fetcher():
    from app.core.PlaywrightDriver import AsyncPlaywrightDriver

    BASE_DATA_DIR = r"/driver/playwright_data"

    async with AsyncPlaywrightDriver(base_data_dir=BASE_DATA_DIR) as driver:
        await driver.launch_browser(viewport_type="pc")

        context = await driver.create_platform_context(
            platform_name="weibo",
            user_data_dir=f"{BASE_DATA_DIR}/weibo_data",
        )

        page = await context.new_page()

        get_hot = AsyncWeiboGetHot(page)
        result = await get_hot.get_hot_title_list(1, 10)
        print(result)
        result = await get_hot.get_hot_content_list(result[0]["href"])
        print(result)


if __name__ == '__main__':
    asyncio.run(test_weibo_hot_fetcher())
