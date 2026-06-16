"""
测试 PromptManager

通过 mock 文件读取行为来隔离测试，不需要真实文件。
"""

import pytest
import json
from unittest.mock import patch, mock_open

from app.core.prompt_manager.manager import PromptManager


@pytest.fixture
def mock_registry():
    return {
        "prompts": [
            {
                "id": "zhihu_answer",
                "name": "知乎回答",
                "description": "知乎问答提示词",
                "file": "zhihu/answer.json",
                "platform": "zhihu",
                "type": "answer",
                "version": 1,
            }
        ]
    }


@pytest.fixture
def mock_prompt_content():
    """字段必须与 Prompt 数据模型严格一致"""
    return {
        "id": "zhihu_answer",
        "name": "知乎回答创作提示词",
        "platform": "zhihu",
        "category": "content_creation",
        "version": "1.0.0",
        "created_at": "2026-05-13T10:17:27.396866+00:00",
        "updated_at": "2026-05-13T10:19:57.706911+00:00",
        "author": "system",
        "tags": ["创作", "知乎", "回答", "真人手写感"],
        "variables": [
            {"name": "hot_title", "description": "热点标题", "required": True},
            {"name": "hot_content", "description": "热点详细内容列表", "required": True},
        ],
        "content": "你是一个知乎回答专家，请用接地气的方式回答用户问题。",
        "metadata": {"token_count": 2800, "optimization_round": 0},
    }


class TestPromptManager:
    """测试提示词管理器（mock 文件系统）"""

    @staticmethod
    def _default_mock(*args, **kwargs):
        """对未匹配的文件（如日志）返回空 mock"""
        return mock_open(read_data="").return_value

    def test_get_prompt(self, mock_registry, mock_prompt_content):
        """成功获取提示词"""
        manager = PromptManager()
        prompt = manager.get_prompt("zhihu_answer")

        assert prompt.id == "zhihu_answer"
        assert prompt.name == "知乎回答创作提示词"
        assert prompt.platform == "zhihu"
        assert prompt.version == "1.0.0-rb"
        assert "创作" in prompt.tags
