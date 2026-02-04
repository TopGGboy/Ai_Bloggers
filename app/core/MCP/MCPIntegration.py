import json
import os
import re
from typing import Any, Dict, List, Tuple

from app.core.MCP.ToolRegistry import create_tool_registry


class MCPIntegration:
    """MCP工具集成类"""

    def __init__(self, client: Any = None, model_name: str = None):
        """初始化MCP集成"""
        # 延迟创建工具注册器实例，避免循环依赖
        self.client = client
        self.model_name = model_name
        self.tools = None
        self.tool_functions = None

        # 只有在提供了client和model时才初始化工具
        if client is not None and model is not None:
            self._initialize_tools()

    def _initialize_tools(self):
        """初始化工具"""
        try:
            # 获取工具注册器创建函数
            tool_registry = create_tool_registry(self.client, self.model)

            # 获取工具定义和函数映射
            self.tools = tool_registry.get_tools()
            self.tool_functions = tool_registry.get_all_tool_functions()
        except Exception as e:
            print(f"初始化MCP工具时出错: {e}")
            self.tools = []
            self.tool_functions = {}

    def get_tools(self) -> List[Dict]:
        """获取所有工具定义"""
        if self.tools is None:
            return []
        return self.tools

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        执行工具函数

        Args:
            tool_name: 工具函数名
            arguments: 函数参数

        Returns:
            函数执行结果
        """
        if self.tool_functions is None or tool_name not in self.tool_functions:
            return f"未知的工具: {tool_name}"
            # raise ValueError(f"未知的工具: {tool_name}")

        try:
            # 获取对应的工具函数
            tool_func = self.tool_functions[tool_name]

            # 调用工具函数
            result = tool_func(**arguments)

            # 如果结果是列表或其他复杂类型，转换为字符串
            if isinstance(result, (list, dict)):
                return json.dumps(result, ensure_ascii=False, indent=2)
            else:
                return str(result)
        except Exception as e:
            return f"执行工具时出错: {str(e)}"

    def chat_with_tools(self,
                        client: Any,
                        model: str,
                        user_prompt: str,
                        system_prompt: str = "You are a helpful assistant with access to tools.",
                        max_iterations: int = 50,
                        temperature: float = 0.7) -> Tuple[str, List[Dict]]:
        """
        与大模型进行对话，自动处理工具调用

        Args:
            client: 大模型客户端
            model: 模型名称
            user_prompt: 用户问题
            system_prompt: 系统提示词
            max_iterations: 最大迭代次数
            temperature: 温度参数

        Returns:
            包含最终回复和完整消息历史的元组
        """
        # 如果尚未初始化工具，则在此处初始化
        if self.tools is None or self.tool_functions is None:
            self.client = client
            self.model = model
            self._initialize_tools()

        # 初始化消息历史为空
        current_messages = []

        for iteration in range(max_iterations):
            # 调用大模型
            content, current_messages = get_response_from_llm(
                user_prompt=user_prompt if iteration == 0 else None,  # 首次调用传递用户问题，后续调用传递None
                client=client,
                model=model,
                system_prompt=system_prompt,
                msg_history=current_messages,  # 传递完整的消息历史
                tools=self.tools,
                temperature=temperature
            )

            # 检查是否有工具调用
            last_message = current_messages[-1]
            if "tool_calls" not in last_message or not last_message["tool_calls"]:
                # 没有工具调用，返回最终回复
                return content, current_messages

            # 处理工具调用
            tool_results = []
            for tool_call in last_message["tool_calls"]:
                tool_name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    arguments = {}

                # 执行工具
                tool_result = self.execute_tool(tool_name, arguments)

                # 添加工具结果到消息列表
                tool_results.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result,
                    "name": tool_name
                })

            # 将工具结果添加到消息历史
            current_messages.extend(tool_results)

        # 达到最大迭代次数
        return current_messages[-1].get("content", "达到最大迭代次数"), current_messages
