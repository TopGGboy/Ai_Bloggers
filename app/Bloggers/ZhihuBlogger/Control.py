import time
import json
import os

from app.Bloggers.ZhihuBlogger.Login import Login
from app.Bloggers.ZhihuBlogger.GetHot import GetHot
from app.Bloggers.ZhihuBlogger.SendEssay import SendEssay
from app.core.ChatWithAi import ChatWithAi
from app.core.Config import AppConfig
from app.tools.Str2Md import Str2Md
from app.tools.LoggingConfig import LoggingConfig


class Control:
    def __init__(self, driver, md_path):
        # 初始化各功能组件
        self.Zhihu_Login = Login(driver=driver)
        self.Zhihu_GetHot = GetHot(driver=driver)
        self.Zhihu_SendEssay = SendEssay(driver=driver)
        self.Zhihu_ai = ChatWithAi(api_key="sk-af0cc0ea7d764e4093ce7eca05f07d0b")
        self.str_2_md = Str2Md()
        self.log = LoggingConfig(log_file_path=AppConfig.LOGFILEPATH).get_logger()

        # 基础配置
        self.md_path = md_path
        self.driver = driver
        self.url = "https://www.zhihu.com/hot"

        # 用户输入相关状态
        self.titles = None
        self.user_input = ""
        self.start_index = None
        self.end_index = None
        self.hot_titles = None

    def __init_run(self):
        """执行初始化流程：登录 + 获取用户输入"""
        # self.Zhihu_Login.run()  # 登录
        print("请输入一个数字监控单个标题，或者输入一个范围（例如 1-3）监控多个标题。")
        self.user_input = input("请输入: ").strip()

        if '-' in self.user_input:
            self.__handle_range_input()
        else:
            self.__handle_single_input()

    def __mon_hot(self):
        """持续监控热榜变化，并触发AI生成和发布流程"""
        count = 0
        while True:
            count += 1
            print(f"第 {count} 次检测")
            self.log.info(f"第 {count} 次检测")
            self.driver.get(self.url)

            # 1. 持久化保存 热榜标题
            self.__save_hot_title()
            # 2. 检查热榜标题变化
            if self.start_index and self.end_index:
                self.__check_hot_titles()
            else:
                self.__check_hot_single_title()

            # 每隔 10 min 检测一次
            # time.sleep(600)

    def __handle_range_input(self):
        """处理范围输入，如 1-3"""
        try:
            self.start_index, self.end_index = map(int, self.user_input.split('-'))
            self.titles = ["1"] * (self.end_index - self.start_index + 1)
        except ValueError:
            print("输入格式错误，请输入一个数字或一个范围（例如 1-3）。")
            self.log.error("输入格式错误，请输入一个数字或一个范围（例如 1-3）。")

    def __handle_single_input(self):
        """处理单个数字输入"""
        try:
            self.start_index = int(self.user_input)
            self.titles = "1"
        except ValueError:
            print("输入格式错误，请输入一个数字或一个范围（例如 1-3）。")
            self.log.error("输入格式错误，请输入一个数字或一个范围（例如 1-3）。")

    def __check_hot_titles(self):
        """检查热榜标题变化"""
        hot_titles = self.Zhihu_GetHot.get_hot_title_list(self.start_index, self.end_index)
        new_hot_titles = [hot_title['title'] for hot_title in hot_titles]

        for index in range(0, self.end_index - self.start_index + 1):
            new_title = new_hot_titles[index]
            if new_title != self.hot_titles[index]:
                self.log.info(f"检测到榜单 {index + 1} 发生变化")
                self.hot_titles[index] = new_title
                # self.__generate_and_publish(new_title, index)

    def __check_hot_single_title(self):
        """检查单个热榜标题变化"""
        new_title = self.Zhihu_GetHot.get_hot_title_list(self.start_index, self.start_index)
        if new_title[0]['title'] != self.hot_titles[0]:
            self.log.info(f"检测到榜单 {self.start_index} 发生变化")
            self.hot_titles[0] = new_title
            # self.__generate_and_publish(new_title, self.start_index)

    def __save_hot_title(self, hot_titles_file="./hot_titles.json"):
        """
        持久化保存 热榜标题
        hot_titles_file: 热榜标题文件路径
        """
        # 如果没有传入标题且文件存在， 读取历史数据
        if not self.hot_titles and os.path.exists(hot_titles_file):
            try:
                with open(hot_titles_file, "r", encoding="utf-8") as f:
                    self.hot_titles = json.load(f)

                # 判断列表长度， 如果长度小于 self.start_index， 则填充 None
                if not self.end_index:
                    if len(self.hot_titles) >= self.start_index:
                        self.hot_titles = [self.hot_titles[self.start_index - 1]]
                    else:
                        self.hot_titles = [None]

                else:
                    if len(self.hot_titles) <= self.end_index - self.start_index + 1:
                        self.hot_titles += [None] * (self.end_index - self.start_index + 1 - len(self.hot_titles))
                    else:
                        self.hot_titles = self.hot_titles[0:self.end_index - self.start_index + 1]

            except Exception as e:
                self.log.error(f"读取热榜标题文件失败: {e}")
        # 如果没有传入标题且文件不存在， 创建文件
        elif not self.hot_titles:
            try:
                with open(hot_titles_file, "w", encoding="utf-8") as f:
                    json.dump([], f, ensure_ascii=False, indent=4)
            except Exception as e:
                self.log.error(f"创建热榜标题文件失败: {e}")
        else:
            # 保存热榜标题到文件
            try:
                with open(hot_titles_file, 'w', encoding='utf-8') as f:
                    json.dump(self.hot_titles, f, ensure_ascii=False, indent=4)
                self.log.info(f"保存热榜标题成功，共 {len(self.hot_titles)} 个标题")
            except Exception as e:
                self.log.error(f"保存热榜标题失败: {e}")

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
