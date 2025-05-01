class Str2Md:
    def __init__(self):
        pass

    def save_2_md(self, str_content, file_name="example.md"):
        """
        将文本内容保存到Markdown文件
        """
        try:
            with open(file_name, 'w', encoding='utf-8') as f:
                f.write(str_content)
            print(f"文本内容已保存到Markdown文件：{file_name}")
        except IOError as e:
            print(f"保存Markdown文件时发生错误：{e}")
        except Exception as e:
            print(f"发生未知错误：{e}")

    def read_md(self, file_name="example.md"):
        """
        读取Markdown文件并返回内容
        """
        try:
            with open(file_name, 'r', encoding='utf-8') as f:
                content = f.read()
            print(f"已读取Markdown文件：{file_name}")
            return content
        except IOError as e:
            print(f"读取Markdown文件时发生错误：{e}")
            return None
        except Exception as e:
            print(f"发生未知错误：{e}")
            return None
