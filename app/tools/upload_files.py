import os
import time
from typing import Optional

from pywinauto import Application
from pywinauto.timings import TimeoutError
from pywinauto.findwindows import ElementNotFoundError


class UploadFiles:
    DEFAULT_WINDOW_CLASS = "#32770"

    def __init__(self, window_class: str = DEFAULT_WINDOW_CLASS):
        """
        初始化文件上传器。

        :param window_class: 文件选择对话框的窗口类名，默认为 "#32770"
        """
        self.window_class = window_class
        self.dlg = None  # 对话框对象，延迟加载

    def __connect_to_dialog(self) -> bool:
        """
        连接到系统文件选择对话框窗口。

        :return: 成功连接返回 True，否则 False
        """
        try:
            app = Application(backend='win32').connect(class_name=self.window_class)
            self.dlg = app.window(class_name=self.window_class)
            return True
        except TimeoutError:
            print("连接应用程序超时，请检查是否已弹出文件选择对话框。")
            return False

    def set_file_path(self, file_path: str) -> bool:
        """
        设置文件路径到文件选择框。

        :param file_path: 文件路径字符串
        :return: 成功设置返回 True，否则 False
        """
        if not os.path.exists(file_path):
            print(f"指定的文件路径不存在：{file_path}")
            return False

        try:
            file_edit = self.dlg.ComboBoxEx.ComboBox.Edit
            file_edit.set_edit_text(file_path)
            return True
        except (AttributeError, ElementNotFoundError) as e:
            print(f"无法找到文件输入框控件：{e}")
            return False

    def __submit_file_selection(self) -> bool:
        """
        点击“打开”按钮提交文件选择。

        :return: 成功点击返回 True，否则 False
        """
        try:
            open_button = self.dlg.Button2
            time.sleep(2)
            open_button.click()
            print("文件路径已设置并点击了“打开”按钮。")
            return True
        except (AttributeError, ElementNotFoundError) as e:
            print(f"无法找到“打开”按钮控件：{e}")
            return False

    def run(self, file_path: str) -> bool:
        """
        执行完整的文件上传流程。

        :param file_path: 要上传的文件路径
        :return: 成功上传返回 True，否则 False
        """
        if not self.__connect_to_dialog():
            return False
        if not self.set_file_path(file_path):
            return False
        if not self.__submit_file_selection():
            return False
        return True


def test_file_uploader():
    uploader = UploadFiles()
    file_path = r"D:\竞赛\泰迪杯\2025\B题\解题\第二题\第二题.docx"
    success = uploader.run(file_path)
    if success:
        print("✅ 文件上传成功。")
    else:
        print("❌ 文件上传失败。")


if __name__ == '__main__':
    test_file_uploader()
