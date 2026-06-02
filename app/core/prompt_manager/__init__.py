"""
提示词核心管理模块

提供全局单例访问入口:

    from app.core.prompt_manager import get_prompt_manager
    pm = get_prompt_manager()
    prompt = pm.get_prompt("zhihu_answer")
    print(prompt.content)
"""

from .manager import PromptManager
from .models import Prompt, VersionRecord, ChangeInfo, DiffResult
from .version_control import PromptVersionControl

# 全局单例
_manager_instance: PromptManager | None = None


def get_prompt_manager() -> PromptManager:
    """获取全局唯一的 PromptManager 实例 (懒初始化单例模式)"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = PromptManager()
    return _manager_instance


__all__ = [
    "PromptManager",
    "Prompt",
    "VersionRecord",
    "ChangeInfo",
    "DiffResult",
    "PromptVersionControl",
    "get_prompt_manager",
]
