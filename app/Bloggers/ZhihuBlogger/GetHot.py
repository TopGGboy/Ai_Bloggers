import time

from typing import Optional, List
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By

from app.tools.ElementWaiter import ElementWaiter
from app.tools.LoggingConfig import LoggingConfig
from app.core.Config import AppConfig


class GetHot:
    def __init__(self, driver, logging=False):
        """
        初始化GetHot类，获取知乎热榜信息
        :param driver: WebDriver实例
        """
        self.driver = driver
        self.url = r"https://www.zhihu.com/hot"
        self.waiter = ElementWaiter(self.driver)
        self.log = LoggingConfig(log_file_path=AppConfig.LOGFILEPATH).get_logger()
        self.logging = logging

    def get_hot_title_list(self, begin, end):
        """
        获取指定范围内的热榜标题

        :param begin: 开始序号(min: 1)
        :param end: 结束序号(max: 30)
        :return: 热榜标题列表
        """
        try:
            self.driver.get(self.url)
            self.waiter.wait_for_element(By.CSS_SELECTOR, "div.HotList-list")

            html_data = self.driver.page_source
            result = self.__parse_hot_title_list(html_data)

            if self.logging:
                self.log.info(f"获取知乎热榜标题成功")
            return result[begin - 1:end]
        except Exception as e:
            if self.logging:
                self.log.error(f"获取知乎热榜失败: {e}")
            return []

    def get_hot_content(self, href):
        """
        获取知乎热榜内容
        :param href: 热榜链接
        :return: 热榜内容{"question_head": 问题简介, "content": 热榜内容}
        """
        try:
            self.driver.get(href)
            self.waiter.wait_for_element(By.CSS_SELECTOR, "div.List-item")

            # 1. 点击展开
            self.waiter.safe_click(By.XPATH, """//button[contains(text(),'显示全部')]""")

            time.sleep(1)

            html_data = self.driver.page_source

            result = self.__parse_hot_content(html_data)

            if self.logging:
                self.log.info(f"获取知乎热榜内容成功")
            return result
        except Exception as e:
            if self.logging:
                self.log.error(f"获取知乎热榜内容失败: {e}")
            return []

    def __parse_hot_title_list(self, hot_title_html):
        """
        解析知乎热榜标题列表页面

        :param hot_title_html: 热榜标题列表页面HTML代码
        :return:
        """
        soup = BeautifulSoup(hot_title_html, 'html.parser')

        # 找到热搜列表容器
        hot_list_container = soup.find("div", class_="HotList-list")
        if not hot_list_container:
            return []

        # 获取所有搜索条目
        hot_items = hot_list_container.find_all("section", class_="HotItem")

        result = []
        for index, item in enumerate(hot_items):
            # 提取标题
            title_elem = item.find("h2", class_="HotItem-title")
            title = title_elem.text.strip() if title_elem else ""

            # 提取链接
            link_elem = item.find("a", href=True)
            href = link_elem["href"] if link_elem else ""

            # 如果链接是相对路径，转换为绝对路径
            if href and not href.startswith("http"):
                href = "https://www.zhihu.com" + href

            result.append({
                "title": title,
                "href": href
            })

        return result

    def __parse_hot_content(self, hot_content_html):
        """
        解析知乎热榜内容页面
        :param hot_content_html: 热榜内容页面HTML代码
        :return: {"question_head": 问题简介, "content": 热榜内容}
        """
        soup = BeautifulSoup(hot_content_html, 'html.parser')

        list_container = soup.find("div", class_="css-0", role="list")
        hot_items = list_container.find_all("div", class_="List-item")

        hot_contents = []

        for item in hot_items:
            content_html = item.find("div", class_="RichContent-inner")
            hot_contents.append(content_html.text)

        question_head = None
        content_span = soup.find('span', class_='RichText ztext css-10o75c2')

        if content_span:
            question_head = content_span.text

        result = {
            "question_head": question_head,
            "content": hot_contents
        }

        return result

    def get_hot_title(self, num) -> Optional[str]:
        """
        获取指定序号的知乎热榜标题。

        :param num:  热榜条目序号（从1开始）
        :return: 标题文本，若未找到或超时则返回 None
        """
        try:
            # 定位到标题元素
            title_element = self.waiter.wait_for_element(By.XPATH,
                                                         f'//section[@class="HotItem"][{num}]//h2[@class="HotItem-title"]')
            # 返回标题文本
            return title_element.text
        except Exception as e:
            print(f"获取标题失败: {e}")
            return None

    def get_hot_titles_in_range(self, start, end) -> List[str]:
        """
        获取指定范围内的热榜标题
        :param start: 范围的起始序号
        :param end: 范围的结束序号
        """
        titles = []
        for num in range(start, end + 1):
            title = self.get_hot_title(num)
            if title:
                titles.append(title)
        return titles


def test_zhihu_hot_fetcher():
    from app.core.EdgeDriver import EdgeDriver

    edgedriver = EdgeDriver(edge_driver_path=r'../../../driver/edgedriver/msedgedriver.exe')
    driver = edgedriver.control_Edge()

    get_hot = GetHot(driver, logging=True)

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
    4. ai生成文案
    """
    hot_title_lists = get_hot.get_hot_title_list(1, 1)
    print(hot_title_lists)
    print(hot_title_lists[0]["href"])
    hot_content = get_hot.get_hot_content(hot_title_lists[0]["href"])
    print(hot_content)


if __name__ == '__main__':
    test_zhihu_hot_fetcher()
