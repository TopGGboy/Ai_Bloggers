from selenium.webdriver.common.by import By

from app.tools.ElementWaiter import ElementWaiter


class GetHot:
    def __init__(self, driver):
        """
        初始化GetHot1类，获取知乎热榜信息
        :param driver: WebDriver实例
        """
        self.driver = driver
        self.url = r"https://www.zhihu.com/hot"
        self.waiter = ElementWaiter(self.driver)
        self.driver.get(self.url)
        self.hot_titles = []

    def get_hot_title(self, num):
        """
        获取指定序号的热榜标题
        :param num: 热榜标题的序号
        :return: 标题文本或None
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

    def get_hot_titles_in_range(self, start, end):
        """
        获取指定范围内的热榜标题
        :param start: 范围的起始序号
        :param end: 范围的结束序号
        """
        for num in range(start, end + 1):
            title = self.get_hot_title(num)
            if title:
                self.hot_titles.append(title)

    def run(self, num_or_range):
        """
        获取指定序号或范围内的热榜标题
        :param num_or_range: 可以是一个整数（表示获取单个标题）或一个包含两个整数的元组（表示获取一个范围内的标题）
        """
        if isinstance(num_or_range, int):
            title = self.get_hot_title(num_or_range)
            if title:
                return title
        elif isinstance(num_or_range, tuple) and len(num_or_range) == 2:
            start, end = num_or_range
            self.get_hot_titles_in_range(start, end)
            return self.hot_titles
        else:
            print("输入无效，请输入一个数字或一个范围。")


if __name__ == '__main__':
    from app.core.EdgeDriver import EdgeDriver

    edgedriver = EdgeDriver(edge_driver_path=r'../../../driver/edgedriver/msedgedriver.exe')
    driver = edgedriver.control_Edge()

    get_hot = GetHot(driver)

    title = get_hot.run((1, 3))
    print(title)
