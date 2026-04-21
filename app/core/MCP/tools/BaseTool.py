"""
MCP 工具基类
所有 MCP 工具都应继承此类或遵循其接口约定（duck typing）
"""

from abc import ABC, abstractmethod
from typing import Callable, Any


class BaseTool(ABC):
    """
    工具基类

    子类需定义:
        tool_name: str          — 对应 maps.py 中 function.name 的值
        get_function() -> Callable — 返回给 ToolRegistry 注册的函数对象

    可选覆写:
        required_config_keys    — 声明从 YAML tool_config 中提取哪些字段
        create_from_config()    — 自定义工厂方法（默认用 inspect 自动匹配）
    """

    # 子类必须覆盖：工具名称，对应 maps.py / ALL_TOOLS_MAP 中的 key
    tool_name: str = ""

    # 子类可选覆盖：声明构造函数需要哪些配置 key
    # 留空 [] 表示不自动提取，由 create_from_config 或 _create_instance 手动处理
    required_config_keys: list[str] = []

    @abstractmethod
    def get_function(self) -> Callable[..., Any]:
        """
        返回该工具的可调用函数（同步或异步均可）

        ToolRegistry 会把返回值注册到 self.tool_functions[tool_name] 中，
        供 LLM 通过 function calling 调用。
        """

    @classmethod
    def create_from_config(cls, config: dict) -> 'BaseTool':
        """
        工厂方法：根据配置字典创建实例

        默认行为：从 config 中按 required_config_keys 提取参数传入构造函数。
        子类可覆写以实现更复杂的初始化逻辑。
        """
        kwargs = {k: config.get(k) for k in cls.required_config_keys if k in config}
        return cls(**kwargs)
