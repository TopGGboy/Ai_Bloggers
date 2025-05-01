from app.core.EdgeDriver import EdgeDriver
from app.bloggers.zhihu_blogger.Control import Control


class MastControl:
    def __init__(self):
        self.edgedriver = EdgeDriver(edge_driver_path=r'../../driver/edgedriver/msedgedriver.exe')
        self.edge_type = None
        self.driver = None

    def menu(self):
        print("欢迎使用 Ai_Blogger ")
        print("请选择你要使用的Blogger")
        print("1. 控制新浏览器")
        print("2. 控制已经打开的浏览器")
        print("3. 知乎")
        print("0. 退出")

    def run(self):
        while True:
            self.menu()
            choice = int(input("请输入你的选择："))
            if choice == 1:
                self.driver = self.edgedriver.new_Edge()
                self.edge_type = 'new_Edge'
                print(f"当前模式{self.edge_type}")
            elif choice == 2:
                self.driver = self.edgedriver.control_Edge()
                self.edge_type = 'control_Edge'
                print(f"当前模式{self.edge_type}")
            elif choice == 3:
                self.Zhihu_Blogger()
            elif choice == 0:
                print("欢迎下次使用")
                break
            else:
                print("请输入正确的选择")

    def Zhihu_Blogger(self):
        self.Zhihu_Control = Control(driver=self.driver)
        self.Zhihu_Control.run()


if __name__ == '__main__':
    mast = MastControl()
    mast.run()
