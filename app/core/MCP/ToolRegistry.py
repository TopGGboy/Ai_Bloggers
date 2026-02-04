"""
工具注册器模块
用于注册和管理所有可用的MCP工具
"""

from typing import Dict, Callable, Any
from app.core.MCP.maps import ALL_TOOLS
from tools import InternetData


class ToolRegistry:
    """工具注册器类"""

    def __init__(self, client: Any, model_name: str):
        # 合并基础工具
        self.tools = ALL_TOOLS
        self.tool_functions: Dict[str, Callable[..., Any]] = {}

        self.client = client
        self.model_name = model_name

        self._register_tools()

    def _register_tools(self):
        """注册所有工具函数"""
        # 创建工具实例
        internet_search = InternetData(client=self.client, model_name=self.model_name)

        # 注册工具函数
        self.tool_functions.update({
            "internet_search": internet_search.get_internet_data,
        })

    def get_tools(self):
        """获取所有工具定义"""
        return self.tools

    def get_tool_function(self, tool_name: str):
        """根据工具名称获取对应的函数"""
        return self.tool_functions.get(tool_name)

    def get_all_tool_functions(self):
        """获取所有工具函数的映射"""
        return self.tool_functions


# 全局工具注册器实例工厂
def create_tool_registry(client: Any, model_name: str) -> ToolRegistry:
    """创建工具注册器实例"""
    return ToolRegistry(client=client, model_name=model_name)
