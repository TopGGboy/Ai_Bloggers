import os
import json
from datetime import datetime

from abc import ABC, abstractmethod
from app.core.config_manager import config
from app.tools.LoggingConfig import LoggingConfig
from app.tools.Str2Md import Str2Md


class BaseWriter(ABC):
    """
    抽象基类：文章写作器基类

    采用模板方法模式：
    - write() 定义完整的写作+保存流程（骨架）
    - _generate_content() 钩子：子类定义如何获取热榜内容并调用 LLM 生成文案
    - _build_json_data() 钩子：子类定义 JSON 中要保存哪些字段
    """

    def __init__(self, platform_name: str):
        # 日志
        self.log = LoggingConfig(log_file_path=config.logfile_path, log_level=config.log_level).get_logger(
            self.__class__.__name__)

        self.file_json_path = config.platforms[platform_name]['paths'].get("essay_file_json")
        self.file_md_path = config.platforms[platform_name]['paths'].get("essay_file_md")

        # 初始化 Str2Md 工具
        self.str_2_md = Str2Md()

    async def write(self, hot_title: dict = None, get_hot_instance=None, write_text_instance=None):
        """
        写作文章 — 模板方法，定义完整流程骨架

        Args:
            hot_title: 热榜标题信息字典，包含 title, href 等
            get_hot_instance: 热榜内容获取实例（传给钩子使用）
            write_text_instance: 文案创作实例（传给钩子使用）

        Returns:
            tuple: (md_path, json_data)
        """
        try:
            self.log.info(f"📖 正在获取内容：{hot_title['title']}")

            # 🔧 钩子1：子类自行决定如何获取内容 + 如何调用 LLM
            raw_content = await self._generate_content(
                hot_title=hot_title,
                get_hot_instance=get_hot_instance,
                write_text_instance=write_text_instance
            )

            # 统一保存为 MD 和 JSON 文件
            sanitized_title = self._sanitize_filename(hot_title['title'])
            json_data = await self._save_content(
                raw_content=raw_content,
                sanitized_title=sanitized_title,
                original_title=hot_title['title']
            )

            return json_data
        except Exception as e:
            self.log.error(f"写作文章失败: {e}")
            return None

    # ==================== 钩子方法 ====================
    async def _generate_content(self, hot_title: dict,
                                get_hot_instance=None,
                                write_text_instance=None):
        """
        🔧 钩子方法1：获取热榜内容并调用 LLM 生成文案

        子类可覆写此方法以自定义：
        - 如何从 get_hot_instance 获取原始数据（字段/结构可能不同）
        - 如何将参数传给 write_text_instance（入参可能不同）
        - 对返回值的后处理（如 JSON 解析等）

        Args:
            hot_title: 热榜信息字典
            get_hot_instance: 热榜内容获取器实例
            write_text_instance: 文案创作器实例

        Returns:
            生成的原始内容（类型由子类决定，会透传给 _build_json_data）

        Raises:
            NotImplementedError: 如果子类未覆写且基类被直接调用
        """
        # 默认实现：保留原有逻辑作为向后兼容
        # （知乎可以直接使用这个默认实现）
        self.log.info("🔍 正在获取热榜详细内容...")
        hot_text_content = await get_hot_instance.get_hot_content_list(hot_title['href'])

        # ✍️ 正在生成文案...
        self.log.info("✍️ 正在生成文案...")
        hot_text, _ = await write_text_instance.write_hot_text_async(
            hot_title['title'],
            hot_text_content['content'],
            hot_text_content['question_head']
        )
        return hot_text

    def _build_json_data(self, original_title: str, raw_content,
                         sanitized_title: str) -> dict:
        """
        🔧 钩子方法2：构建需要持久化到 JSON 的数据结构

        子类可覆写此方法以自定义 JSON 字段。

        Args:
            original_title: 原始标题
            raw_content: _generate_content() 的返回值
            sanitized_title: 清理后的文件名标题

        Returns:
            dict: 要写入 JSON 的数据
        """
        return {
            "title": original_title,
            "content": raw_content,
            "timestamp": datetime.now().isoformat()
        }

    # ==================== 内部方法（一般不需覆写）====================

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

    async def _save_content(self, raw_content, sanitized_title: str,
                            original_title: str):
        """统一保存内容为 JSON 文件"""
        try:
            # 通过钩子构建 JSON 数据
            json_data = self._build_json_data(original_title, raw_content, sanitized_title)
            await self._append_to_json(json_data)
            self.log.info(f"✅ JSON 文件已追加")

            return json_data

        except Exception as e:
            self.log.error(f"保存文件失败：{e}", exc_info=True)
            return None

    async def _append_to_json(self, data: dict):
        """追加数据到 JSON 文件"""
        json_path = self.file_json_path
        os.makedirs(os.path.dirname(json_path), exist_ok=True)

        if not os.path.exists(json_path):
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)

        with open(json_path, 'r', encoding='utf-8') as f:
            content_list = json.load(f)

        content_list.append(data)

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(content_list, f, ensure_ascii=False, indent=2)

        self.log.info(f"内容已追加到：{json_path}")
