"""
工具元数据注册表

职责：
  1. 维护「工具名 → 工具类」的全局映射（新增工具只需在此注册一行）
  2. 提供按平台配置筛选已启用工具的能力

新增工具的步骤：
  1. 在 tools/ 下编写工具类（继承 BaseTool）
  2. 在 maps.py 中添加工具 Schema 定义
  3. 在本文件的 TOOL_CLASS_MAP 中注册一行
  4. 在 Ai_Blogger.yaml 对应平台的 tools 下添加配置
"""

from typing import Type
from app.core.mcp.tools.base_tool import BaseTool

# ============================================================
#  工具名 → 工具类的映射表
#  新增工具在这里添加一行即可
# ============================================================
TOOL_CLASS_MAP: dict[str, Type[BaseTool]] = {
    # "get_internet_data": InternetData,
    # "create_image": AiCreateImage,
    # 未来新工具：
    # "translate": TranslateTool,
    # "summarize": SummarizeTool,
}

# 延迟导入，避免循环依赖 —— 在首次使用时填充 TOOL_CLASS_MAP
_initialized = False


def _lazy_import():
    """延迟导入所有工具类，避免模块加载时的循环引用"""
    global _initialized
    if _initialized:
        return

    from app.core.mcp.tools.internet_data import InternetData
    from app.core.mcp.tools.ai_create_image import AiCreateImage

    TOOL_CLASS_MAP.update({
        "get_internet_data": InternetData,
        "create_image": AiCreateImage,
    })
    _initialized = True


def get_tool_class(tool_name: str) -> Type[BaseTool] | None:
    """获取工具名对应的类"""
    _lazy_import()
    return TOOL_CLASS_MAP.get(tool_name)


def get_all_tool_names() -> list[str]:
    """获取所有已注册的工具名列表"""
    _lazy_import()
    return list(TOOL_CLASS_MAP.keys())


def get_enable_tool_names(platform_tools_config: dict) -> list[str]:
    """
    从某平台的 tools 配置中，筛选出 enabled=True 的工具名列表

    Args:
        platform_tools_config: 平台下的 tools 段，如 config.platforms[zhihu].tools

    Returns:
        已启用的工具名列表，如 ["get_internet_data", "create_image"]

    Example:
        >>> cfg = {"internet_data": {"enabled": True}, "create_image": {"enabled": False}}
        >>> get_enabled_tool_names(cfg)
        ['get_internet_data']
    """
    if not platform_tools_config:
        return []

    enabled = []

    for name, tool_cfg in platform_tools_config.items():
        # 兼容两种写法：
        #   方式A: internet_data: true                    （简写，默认启用）
        #   方式B: internet_data: {enabled: true, ...}   （完整配置）
        if isinstance(tool_cfg, bool):
            if tool_cfg:
                enabled.append(name)
        elif isinstance(tool_cfg, dict):
            if tool_cfg.get("enabled", False):
                enabled.append(name)

    return enabled
