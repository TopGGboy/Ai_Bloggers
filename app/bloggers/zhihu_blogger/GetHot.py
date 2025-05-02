from typing import Optional, List

from selenium.webdriver.common.by import By

from app.tools.ElementWaiter import ElementWaiter


class GetHot:
    def __init__(self, driver):
        """
        初始化GetHot类，获取知乎热榜信息
        :param driver: WebDriver实例
        """
        self.driver = driver
        self.url = r"https://www.zhihu.com/hot"
        self.waiter = ElementWaiter(self.driver)
        self.driver.get(self.url)

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
    edgedriver = EdgeDriver(edge_driver_path=r'../../../driver/edgedriver/msedgedriver.exe')
    driver = edgedriver.control_Edge()
    fetcher = ZhihuHotFetcher(driver)
    fetcher.navigate_to_page()
    title = fetcher.fetch_hot_title(1)
    print(title)
    driver.quit()


if __name__ == '__main__':
    test_zhihu_hot_fetcher()
