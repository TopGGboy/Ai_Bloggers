from enum import Enum


class PlatformMode(Enum):
    """平台运行模式枚举 - 适用于所有社交平台"""
    MONITOR_ONLY = "monitor_only"  # 只监控
    PUBLISH_ONLY = "publish_only"  # 只发布
    MONITOR_AND_PUBLISH = "monitor_and_publish"  # 监控并发布
