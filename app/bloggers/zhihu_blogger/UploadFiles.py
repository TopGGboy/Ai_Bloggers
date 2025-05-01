from pywinauto import Application
from pywinauto.timings import TimeoutError


class UploadFiles:
    def __init__(self):
        pass

    def main(self):
        try:
            # 连接桌面
            app = Application(backend='win32').connect(class_name="#32770")
            self.dlg = app.window(class_name="#32770")
        except TimeoutError:
            print("连接应用程序超时，请检查应用程序是否正常运行。")

    def set_file_path(self, file_path):
        file_edit = self.dlg.ComboBoxEx.ComboBox.Edit
        file_edit.set_edit_text(file_path)

    def click_open_button(self):
        # 定位“打开”按钮，根据 层级关系和属性
        open_button = self.dlg.Button2
        # 点击“打开”按钮
        open_button.click()
        print("文件路径已设置并点击了“打开”按钮。")

    def run(self, file_path):
        self.main()
        self.set_file_path(file_path)
        self.click_open_button()


if __name__ == '__main__':
    upload_file = UploadFiles()
    file_path = r"D:\竞赛\泰迪杯\2025\B题\解题\第二题\第二题.docx"
    upload_file.run(file_path)
