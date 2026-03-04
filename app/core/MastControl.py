from app.core.PlaywrightDriver import PlaywrightDriver
from app.Bloggers.ZhihuBlogger.Control import Control
from app.tools.LoggingConfig import LoggingConfig
from app.core.config_manager import config
from playwright.sync_api import Page


class MastControl:
    def __init__(self, md_path: str = None, playwright_driver_data: str = None):
        self.playwright_driver = PlaywrightDriver(user_data_dir=playwright_driver_data)

        if md_path is None:
            md_path = r'D:\pythonproject\Ai_Blogger\Md'
        self.md_path = md_path

        # 日志配置
        self.log = LoggingConfig(log_file_path=config.logfile_path).get_logger("MastControl")

        self.context = None
        self.page = None
        self.edge_type = None

    def show_welcome(self):
        print("=" * 40)
        print("       欢迎使用 Ai_Blogger")
        print("=" * 40)

    def choose_browser_mode(self):
        print("\n请选择浏览器控制方式：")
        print("1. 控制新的浏览器实例")
        print("2. 控制已打开的浏览器")
        choice = input("请输入你的选择（1 或 2）：").strip()
        if choice == '1':
            self.context, self.page = self.playwright_driver.launch_browser()
            self.edge_type = 'new_Edge'
            self.log.info(f"当前模式：{self.edge_type}")
            print(f"✅ 当前模式：{self.edge_type}")
        elif choice == '2':
            self.context, self.page = self.playwright_driver.connect_existing_browser()
            self.edge_type = 'control_Edge'
            self.log.info(f"当前模式：{self.edge_type}")
            print(f"✅ 当前模式：{self.edge_type}")
        else:
            print("❌ 输入无效，请重新选择。")
            self.log.info("输入无效，请重新选择。")
            return self.choose_browser_mode()

    def choose_platform(self):
        print("\n请选择你要操作的平台：")
        print("1. 知乎")
        # 后续可扩展其他平台
        print("0. 返回上一级")
        choice = input("请输入你的选择：").strip()

        if choice == '1':
            self.run_zhihu_blogger()
        elif choice == '0':
            return
        else:
            print("❌ 输入无效，请重新选择。")
            self.log.info("输入无效，请重新选择。")
            self.choose_platform()

    def run_zhihu_blogger(self):
        print("🔄 正在启动知乎 Blogger...")
        self.log.info("正在启动知乎 Blogger...")
        # 传递 page 对象而不是 driver
        zhihu_control = Control(page=self.page, md_path=self.md_path)
        zhihu_control.run()

    def run(self):
        self.show_welcome()

        # 第一步：选择浏览器控制方式
        self.choose_browser_mode()

        # 第二步：选择平台并执行对应操作
        self.choose_platform()

        print("👋 感谢使用 Ai_Blogger，欢迎下次再见！")
        self.log.info("感谢使用 Ai_Blogger，欢迎下次再见！")

        # 清理资源
        self.edgedriver.quit()


if __name__ == '__main__':
    mast = MastControl()
    mast.run()
