from app.bloggers.zhihu_blogger.Login import Login
from app.bloggers.zhihu_blogger.GetHot import GetHot
from app.bloggers.zhihu_blogger.SendEssay import SendEssay
from app.core.ChatWithAi import ChatWithAi
from app.tools.Str2Md import Str2Md


class Control:
    def __init__(self, driver, md_path):
        self.Zhihu_Login = Login(driver=driver)
        self.Zhihu_GetHot = GetHot(driver=driver)
        self.Zhihu_SendEssay = SendEssay(driver=driver)
        self.Zhihu_ai = ChatWithAi(api_key="sk-af0cc0ea7d764e4093ce7eca05f07d0b")
        self.str_2_md = Str2Md()

        self.md_path = md_path
        self.driver = driver
        self.url = r"https://www.zhihu.com/hot"

        self.titles = None

        self.num = None  # 单个标题
        self.start = None  # 多个标题起始位
        self.end = None  # 多个标题结束位

    def init_run(self):
        # 登录
        self.Zhihu_Login.run()

        # 提示用户输入
        print("请输入一个数字监控单个标题，或者输入一个范围（例如 1-3）监控多个标题。")
        # 读取用户输入
        self.user_input = input("请输入: ").strip()

        if '-' in self.user_input:
            try:
                self.start, self.end = map(int, self.user_input.split('-'))
                self.titles = []
                for i in range(self.start, self.end + 1):
                    self.titles.append("1")
            except ValueError:
                print("输入格式错误，请输入一个数字或一个范围（例如 1-3）。")
        else:
            try:
                self.num = int(self.user_input)
                self.titles = '1'
            except ValueError:
                print("输入格式错误，请输入一个数字或一个范围（例如 1-3）。")

    def mon_hot(self):
        count = 0
        while True:
            count += 1
            print(f"第 {count} 次检测")
            # 刷新热榜
            self.driver.get(self.url)
            if str == type(self.titles):
                new_title = self.Zhihu_GetHot.get_hot_title(int(self.user_input))
                if new_title != self.titles:
                    print(f"检测到榜 {int(self.user_input)} 变化")
                    self.titles = new_title
                    # ai生成文案
                    response = self.Zhihu_ai.run(new_title)
                    # response = "2"
                    # 保存位Md文件
                    self.str_2_md.save_2_md(response, file_name=f"{self.md_path}/example_{int(self.user_input)}.md")
                    # 上传文件并发布
                    self.Zhihu_SendEssay.run(int(self.user_input),
                                             f"D:\pythonproject\Ai_Blogger\Md\example_{int(self.user_input)}.md")

            elif list == type(self.titles):
                for num in range(self.start, self.end + 1):
                    new_title = self.Zhihu_GetHot.get_hot_title(num)
                    if new_title != self.titles[num % len(self.titles) - 1]:
                        print(f"检测到榜 {num} 改变")
                        self.titles[num % len(self.titles) - 1] = new_title
                        # ai生成文案
                        response = self.Zhihu_ai.run(new_title)
                        # response = "2"
                        # 保存位Md文件
                        self.str_2_md.save_2_md(response, file_name=f"{self.md_path}/example_{num}.md")
                        # 上传文件并发布
                        self.Zhihu_SendEssay.run(num,
                                                 f"D:\pythonproject\Ai_Blogger\Md\example_{num}.md")

    def run(self):
        self.init_run()
        self.mon_hot()


if __name__ == '__main__':
    from app.core.EdgeDriver import EdgeDriver

    edgedriver = EdgeDriver(edge_driver_path=r'../../../driver/edgedriver/msedgedriver.exe')
    driver = edgedriver.control_Edge()

    ZhihuControl = Control(driver=driver, md_path=r"../../../Md")

    ZhihuControl.run()
