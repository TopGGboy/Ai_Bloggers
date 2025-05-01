from app.bloggers.zhihu_blogger.Login import Login


class MastControl:
    def __init__(self):
        self.Zhihu_Login = Login()

    def menu(self):
        print("欢迎使用 Ai_Blogger ")
        print("请选择你要使用的Blogger")
        print("1. 知乎")
        print("0. 退出")

    def run(self):
        while True:
            self.menu()
            choice = int(input("请输入你的选择："))
            if choice == 1:
                self.Zhihu_Login.run()
            elif choice == 0:
                print("欢迎下次使用")
                break
            else:
                print("请输入正确的选择")


if __name__ == '__main__':
    mast = MastControl()
    mast.run()
