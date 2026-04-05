import os
import json

from abc import ABC, abstractmethod
from app.core.config_manager import config
from app.tools.LoggingConfig import LoggingConfig
from app.tools.Str2Md import Str2Md


class BaseWriter(ABC):
    """
    抽象基类：文章写作器基类
    """

    def __init__(self, platform_name: str):
        # 日志
        self.log = LoggingConfig(log_file_path=config.logfile_path, log_level=config.log_level).get_logger(
            self.__class__.__name__)

        self.file_json_path = config.platforms[platform_name]['paths'].get("essay_file_json")
        self.file_md_path = config.platforms[platform_name]['paths'].get("essay_file_md")

        # 初始化 Str2Md 工具
        self.str_2_md = Str2Md()

    async def write(self, hot_title: dict = None, Get_Hot_Class=None, Write_Text_Class=None):
        """
        写作文章


        Args:
            hot_title: 热榜标题信息字典，包含 title, href 等
            Get_Hot_Class: 知乎热榜获取器类
            Write_Text_Class: 知乎文案创作器类
        """
        try:
            self.log.info(f"📖 正在获取内容：{hot_title['title']}")
            hot_text_content = await Get_Hot_Class.get_hot_content_list(hot_title['href'])

            # AI生成文案
            self.log.info("✍️ 正在生成文案...")
            hot_text, _ = await Write_Text_Class.write_hot_text_async(
                hot_title['title'],
                hot_text_content['content'],
                hot_text_content['question_head']
            )

            # 统一保存为 MD 和 JSON 文件
            sanitized_title = self._sanitize_filename(hot_title['title'])
            md_path, json_data = await self._save_content(hot_text, sanitized_title, hot_title['title'])

            return md_path, json_data
        except Exception as e:
            self.log.error(f"写作文章失败: {e}")

    def _sanitize_filename(self, title: str) -> str:
        """清理标题中的特殊字符，使其适合作为文件名"""
        invalid_chars = r'<>"|*?/\\:'
        sanitized = title
        for char in invalid_chars:
            sanitized = sanitized.replace(char, '_')

        sanitized = ' '.join(sanitized.split())

        max_length = 200
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]

        return sanitized

    async def _save_content(self, content: str, sanitized_title: str, original_title: str):
        """
        统一保存内容为 MD 和 JSON 文件

        Args:
            content: 生成的文章内容
            sanitized_title: 清理后的标题（用于文件名）
            original_title: 原始标题（用于 JSON 内容）
        """
        try:
            # 保存为 MD 文件
            md_path = os.path.join(self.file_md_path, f"{sanitized_title}.md")
            self.str_2_md.save_2_md(content, md_path)
            self.log.info(f"✅ Markdown 文件已保存：{md_path}")

            # 保存为 JSON 文件（追加模式）
            json_data = {
                "title": original_title,
                "content": content,
                "timestamp": datetime.now().isoformat()
            }
            await self._append_to_json(json_data)
            self.log.info(f"✅ JSON 文件已追加")

            return md_path, json_data


        except Exception as e:
            self.log.error(f"保存文件失败：{e}")

    async def _append_to_json(self, data: dict):
        """
        追加数据到 JSON 文件（如果文件不存在则创建）

        Args:
            data: 要追加的字典数据
        """
        json_path = self.file_json_path

        # 确保目录存在
        os.makedirs(os.path.dirname(json_path), exist_ok=True)

        # 如果文件不存在，创建空列表
        if not os.path.exists(json_path):
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)

        # 读取现有内容
        with open(json_path, 'r', encoding='utf-8') as f:
            content_list = json.load(f)

        # 追加新数据
        content_list.append(data)

        # 写回文件
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(content_list, f, ensure_ascii=False, indent=2)

        self.log.info(f"内容已追加到：{json_path}")
