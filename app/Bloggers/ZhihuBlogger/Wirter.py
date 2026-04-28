import os
import json
from datetime import datetime
from app.tools.LoggingConfig import LoggingConfig
from app.core.config_manager import config
from app.tools.Str2Md import Str2Md
from app.Bloggers.BaseWriter import BaseWriter


class ZhihuWriter(BaseWriter):
    """
    知乎文章写作器

    当前完全继承 BaseWriter 的实现
    预留此类用于未来可能的知乎特定功能扩展
    """

    def __init__(self):
        super().__init__(platform_name="zhihu")

    async def _generate_content(self, hot_title: dict,
                                get_hot_instance=None,
                                write_text_instance=None):
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
        return {
            "title": raw_content["title"],
            "content": raw_content["content"],
            "timestamp": datetime.now().isoformat()
        }
