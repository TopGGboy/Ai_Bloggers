import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from app.core.config_manager import config, ConfigManager
from app.core.multi_platform_manager import MultiPlatformManager, PlatformMode

logger = logging.getLogger(__name__)


def mask_sensitive(value: str) -> str:
    """脱敏显示，保留前4后4位"""
    if not value:
        return ""
    if len(value) <= 8:
        return value[:2] + "****" + value[-2:] if len(value) > 4 else "****"
    return value[:4] + "****" + value[-4:]


def print_json(data: Any):
    """漂亮打印 JSON"""
    print(json.dumps(data, indent=2, ensure_ascii=False))


def get_known_platforms() -> Dict[str, Any]:
    """从配置读取所有已知平台及其配置"""
    p = config.platforms
    return p if isinstance(p, dict) else {}


def _get_project_root() -> Path:
    """推断项目根目录（config.logfile_path.parent = Ai_Blogger/）"""
    return config.logfile_path.parent


async def create_manager(
    md_path: Optional[str] = None,
    base_driver_path: Optional[str] = None,
) -> MultiPlatformManager:
    """创建并初始化 MultiPlatformManager（启动浏览器）"""
    if md_path is None:
        md_path = str(_get_project_root() / "Md")
    if base_driver_path is None:
        base_driver_path = str(config.base_driver_path)

    manager = MultiPlatformManager(md_path=md_path, base_driver_path=base_driver_path)
    await manager.init()
    return manager


async def close_manager(manager: MultiPlatformManager):
    """安全关闭 MultiPlatformManager"""
    try:
        await manager.close_all()
    except Exception:
        pass


def resolve_platform_class(platform_name: str) -> Tuple[type, Any]:
    """平台名 → (control_class, publish_type_enum)"""
    if platform_name == "zhihu":
        from app.bloggers.ZhihuBlogger.Control import ZhihuAsyncControl
        from app.bloggers.ZhihuBlogger.PublishTypeEnums import ZhihuPublishType
        return ZhihuAsyncControl, ZhihuPublishType
    elif platform_name == "weibo":
        from app.bloggers.WeiboBlogger.Control import WeiboAsyncControl
        from app.bloggers.WeiboBlogger.enums import WeiboPublishType
        return WeiboAsyncControl, WeiboPublishType
    else:
        raise ValueError(f"未知平台: {platform_name}")


def parse_platform_mode(mode_str: str) -> PlatformMode:
    """字符串 → PlatformMode 枚举"""
    mapping = {
        "monitor_only": PlatformMode.MONITOR_ONLY,
        "publish_only": PlatformMode.PUBLISH_ONLY,
        "monitor_and_publish": PlatformMode.MONITOR_AND_PUBLISH,
    }
    if mode_str not in mapping:
        valid = ", ".join(mapping.keys())
        raise ValueError(f"无效模式 '{mode_str}'，可选: {valid}")
    return mapping[mode_str]


def get_publish_type_value(platform_name: str, publish_type_enum: type) -> Any:
    """获取发布类型枚举值，用于 register_platform 的 publish_type 参数"""
    if platform_name == "zhihu":
        return publish_type_enum.ARTICLE
    elif platform_name == "weibo":
        return publish_type_enum.ESSAY
    return list(publish_type_enum)[0]


def deep_mask_config(data: Any, sensitive_keys: set) -> Any:
    """递归脱敏配置字典"""
    if isinstance(data, dict):
        return {
            k: mask_sensitive(v) if k in sensitive_keys and isinstance(v, str) and v
            else deep_mask_config(v, sensitive_keys)
            for k, v in data.items()
        }
    elif isinstance(data, list):
        return [deep_mask_config(item, sensitive_keys) for item in data]
    return data


def get_sensitive_leaf_keys() -> set:
    """从 SENSITIVE_FIELDS 中提取叶子 key 名"""
    return {path.split(".")[-1] for path, _, _ in ConfigManager.SENSITIVE_FIELDS}
