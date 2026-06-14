"""
存储层 - 结构化数据持久化

导出:
    storage: AsyncStorageManager 全局单例
    所有 Record 数据类
"""

from app.core.storage.manager import AsyncStorageManager
from app.core.storage.models import (
    ContentRecord,
    PerformanceRecord,
    LearningRecord,
    PublishLogRecord,
    MonitorEventRecord,
    StyleAnchorRecord,
)

# 全局单例
storage = AsyncStorageManager()

__all__ = [
    "AsyncStorageManager",
    "storage",
    "ContentRecord",
    "PerformanceRecord",
    "LearningRecord",
    "PublishLogRecord",
    "MonitorEventRecord",
    "StyleAnchorRecord",
]
