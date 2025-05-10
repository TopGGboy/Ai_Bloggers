import time

from app.bloggers.zhihu_blogger.Login import Login
from app.bloggers.zhihu_blogger.GetHot import GetHot
from app.bloggers.zhihu_blogger.SendEssay import SendEssay
from app.core.ChatWithAi import ChatWithAi
from app.tools.Str2Md import Str2Md


class Control:
    def __init__(self, driver, md_path):
        # 初始化各功能组件
        self.Zhihu_Login = Login(driver=driver)
        self.Zhihu_GetHot = GetHot(driver=driver)
        self.Zhihu_SendEssay = SendEssay(driver=driver)
        self.Zhihu_ai = ChatWithAi(api_key="sk-af0cc0ea7d764e4093ce7eca05f07d0b")
        self.str_2_md = Str2Md()

        # 基础配置
        self.md_path = md_path
        self.driver = driver
        self.url = "https://www.zhihu.com/hot"

        # 用户输入相关状态
        self.titles = None
        self.user_input = ""
        self.start_index = None
        self.end_index = None

    def __init_run(self):
        """执行初始化流程：登录 + 获取用户输入"""
        self.Zhihu_Login.run()  # 登录
        print("请输入一个数字监控单个标题，或者输入一个范围（例如 1-3）监控多个标题。")
        self.user_input = input("请输入: ").strip()

        if '-' in self.user_input:
            self.__handle_range_input()
        else:
            self.__handle_single_input()

    def __handle_range_input(self):
        """处理范围输入，如 1-3"""
        try:
            self.start_index, self.end_index = map(int, self.user_input.split('-'))
            self.titles = ["1"] * (self.end_index - self.start_index + 1)
        except ValueError:
            print("输入格式错误，请输入一个数字或一个范围（例如 1-3）。")

    def __handle_single_input(self):
        """处理单个数字输入"""
        try:
            self.start_index = int(self.user_input)
            self.titles = "1"
        except ValueError:
            print("输入格式错误，请输入一个数字或一个范围（例如 1-3）。")

    def __mon_hot(self):
        """持续监控热榜变化，并触发AI生成和发布流程"""
        count = 0
        while True:
            count += 1
            print(f"第 {count} 次检测")
            self.driver.get(self.url)

            if isinstance(self.titles, str):
                self.__check_and_process_single_title()
            elif isinstance(self.titles, list):
                self.__check_and_process_multiple_titles()

            # 每隔 10 min 检测一次
            time.sleep(600)

    def __check_and_process_single_title(self):
        """检查并处理单个标题的变化"""
        new_title = self.Zhihu_GetHot.get_hot_title(self.start_index)  # 获取当前标题
        if new_title != self.titles:  # 标题发生变化
            print(f"检测到榜单 {self.start_index} 发生变化")
            self.titles = new_title  # 更新标题
            self.__generate_and_publish(new_title, self.start_index)

    def __check_and_process_multiple_titles(self):
        """检查并处理多个标题的变化"""
        for index in range(self.start_index, self.end_index + 1):
            new_title = self.Zhihu_GetHot.get_hot_title(index)  # 获取当前标题
            if new_title != self.titles[index - self.start_index]:  # 标题发生变化
                print(f"检测到榜单 {index} 发生变化")
                self.titles[index - self.start_index] = new_title  # 更新标题
                self.__generate_and_publish(new_title, index)

    def __generate_and_publish(self, title, index):
        """生成文案并保存为Markdown，然后发布文章"""
        response = self.Zhihu_ai.run(title)  # 生成文案
        # response = "这是测试文案"
        file_name = fr"{self.md_path}\example_{index}.md"  # 生成文件名
        self.str_2_md.save_2_md(response, file_name=file_name)  # 保存为Markdown
        self.Zhihu_SendEssay.run(index, file_name)  # 发布文章

    def run(self):
        """主运行入口"""
        self.__init_run()
        self.__mon_hot()


if __name__ == '__main__':
    from app.core.EdgeDriver import EdgeDriver

    edgedriver = EdgeDriver(edge_driver_path=r'../../../driver/edgedriver/msedgedriver.exe')
    driver = edgedriver.control_Edge()

    ZhihuControl = Control(driver=driver, md_path=r"D:\pythonproject\Ai_Blogger\Md")
    ZhihuControl.run()
