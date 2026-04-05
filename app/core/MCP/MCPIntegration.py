import json
import os
import re
from typing import Any, Dict, List, Tuple
import asyncio

from app.tools.LoggingConfig import LoggingConfig
from app.core.config_manager import config
from app.core.MCP.ToolRegistry import create_tool_registry
from app.core.AiAgent import LLM


class MCPIntegration:
    """MCP工具集成类"""

    def __init__(self, client: Any = None, model_name: str = None):
        """初始化MCP集成"""
        # 延迟创建工具注册器实例，避免循环依赖
        self.client = client
        self.model_name = model_name
        self.llm = LLM()
        self.tools = None
        self.tool_functions = None

        self.log = LoggingConfig(log_file_path=config.logfile_path, log_level=config.log_level).get_logger(
            f"{self.__class__.__name__}")

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
            content, current_messages = self.llm.get_response_from_llm(
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
                tool_name = tool_call["function"]["name"]
                try:
                    arguments = json.loads(tool_call["function"]["arguments"])
                except json.JSONDecodeError:
                    arguments = {}

                # 执行工具
                tool_result = self.execute_tool(tool_name, arguments)

                # 添加工具结果到消息列表
                tool_results.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": tool_result,
                    "name": tool_name
                })

            # 将工具结果添加到消息历史
            current_messages.extend(tool_results)

        # 达到最大迭代次数
        return current_messages[-1].get("content", "达到最大迭代次数"), current_messages

    async def chat_with_tools_async(self,
                                    client: Any,
                                    model: str,
                                    user_prompt: str,
                                    system_prompt: str = "You are a helpful assistant with access to tools.",
                                    max_iterations: int = 50,
                                    temperature: float = 0.7,
                                    overall_timeout: int = 600) -> Tuple[str, List[Dict]]:
        """
        异步版本：与大模型进行对话，自动处理工具调用

        Args:
            client: 大模型客户端（必须是 AsyncOpenAI）
            model: 模型名称
            user_prompt: 用户问题
            system_prompt: 系统提示词
            max_iterations: 最大迭代次数
            temperature: 温度参数
            overall_timeout: 整体超时时间（秒），默认 600 秒
        """
        if self.tools is None or self.tool_functions is None:
            self.client = client
            self.model = model
            self._initialize_tools()

        current_messages = []
        llm_instance = LLM()

        for iteration in range(max_iterations):
            # 整体超时检查
            if iteration == 0:
                _start_time = asyncio.get_event_loop().time()

            elapsed = asyncio.get_event_loop().time() - _start_time
            if elapsed > overall_timeout:
                self.log.warning(f"[MCP] 达到整体超时 {overall_timeout}s，当前迭代: {iteration}")
                break

            self.log.info(f"[MCP] ========== 迭代 {iteration + 1}/{max_iterations}，已耗时 {elapsed:.1f}s ==========")

            # 异步调用 LLM
            content, current_messages = await llm_instance.get_response_from_llm_async(
                user_prompt=user_prompt if iteration == 0 else None,
                client=client,
                model=model,
                system_prompt=system_prompt,
                msg_history=current_messages,
                tools=self.tools,
                temperature=temperature
            )
            self.log.debug(f"[MCP] 迭代 {iteration + 1}: LLM 返回完成")

            last_message = current_messages[-1]
            if "tool_calls" not in last_message or not last_message["tool_calls"]:
                self.log.info(f"[MCP] 无 tool_calls，返回最终回复（共 {iteration + 1} 次迭代）")
                return content, current_messages

            # 【关键修改】异步执行工具
            tool_results = []
            for idx, tool_call in enumerate(last_message["tool_calls"]):
                tool_name = tool_call["function"]["name"]
                try:
                    arguments = json.loads(tool_call["function"]["arguments"])
                except json.JSONDecodeError:
                    arguments = {}

                self.log.info(f"[MCP] 执行工具 [{idx + 1}]: {tool_name}，参数: {arguments}")

                # 检查工具函数是否是异步的
                tool_func = self.tool_functions.get(tool_name)
                if tool_func and asyncio.iscoroutinefunction(tool_func):
                    # 异步工具 + 超时
                    tool_result = await asyncio.wait_for(
                        tool_func(**arguments),
                        timeout=600  # 单个工具最多执行 60 秒
                    )
                else:
                    # 同步工具（在后台线程中执行，避免阻塞）+ 超时
                    import concurrent.futures
                    loop = asyncio.get_event_loop()
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        tool_result = await asyncio.wait_for(
                            loop.run_in_executor(
                                executor,
                                lambda: tool_func(**arguments) if tool_func else f"未知的工具：{tool_name}"
                            ),
                            timeout=60  # 单个工具最多执行 60 秒
                        )

                # 截断过长的工具结果日志
                result_preview = str(tool_result)[:200] if tool_result else "(空)"
                self.log.info(f"[MCP] 工具 {tool_name} 执行完成，结果预览: {result_preview}")

                tool_results.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": str(tool_result),
                    "name": tool_name
                })

            current_messages.extend(tool_results)

        self.log.warning(f"[MCP] 达到最大迭代次数 {max_iterations}，强制退出")
        return current_messages[-1].get("content", "达到最大迭代次数"), current_messages

    # async def chat_with_tools_async(self,
    #                                 client: Any,
    #                                 model: str,
    #                                 user_prompt: str,
    #                                 system_prompt: str = "You are a helpful assistant with access to tools.",
    #                                 max_iterations: int = 50,
    #                                 temperature: float = 0.7) -> Tuple[str, List[Dict]]:
    #     """
    #     异步版本：与大模型进行对话，自动处理工具调用
    #
    #     Args:
    #         client: 大模型客户端（必须是 AsyncOpenAI）
    #         model: 模型名称
    #         user_prompt: 用户问题
    #         system_prompt: 系统提示词
    #         max_iterations: 最大迭代次数
    #         temperature: 温度参数
    #
    #     Returns:
    #         包含最终回复和完整消息历史的元组
    #     """
    #     if self.tools is None or self.tool_functions is None:
    #         self.client = client
    #         self.model = model
    #         self._initialize_tools()
    #
    #     current_messages = []
    #     llm_instance = LLM()
    #
    #     for iteration in range(max_iterations):
    #         # 异步调用 LLM
    #         content, current_messages = await llm_instance.get_response_from_llm_async(
    #             user_prompt=user_prompt if iteration == 0 else None,
    #             client=client,
    #             model=model,
    #             system_prompt=system_prompt,
    #             msg_history=current_messages,
    #             tools=self.tools,
    #             temperature=temperature
    #         )
    #
    #         last_message = current_messages[-1]
    #         if "tool_calls" not in last_message or not last_message["tool_calls"]:
    #             return content, current_messages
    #
    #         # 【关键修改】异步执行工具
    #         tool_results = []
    #         for tool_call in last_message["tool_calls"]:
    #             tool_name = tool_call["function"]["name"]
    #             try:
    #                 arguments = json.loads(tool_call["function"]["arguments"])
    #             except json.JSONDecodeError:
    #                 arguments = {}
    #
    #             # 检查工具函数是否是异步的
    #             tool_func = self.tool_functions.get(tool_name)
    #             if tool_func and asyncio.iscoroutinefunction(tool_func):
    #                 # 异步工具
    #                 tool_result = await tool_func(**arguments)
    #             else:
    #                 # 同步工具（在后台线程中执行，避免阻塞）
    #                 import concurrent.futures
    #                 loop = asyncio.get_event_loop()
    #                 with concurrent.futures.ThreadPoolExecutor() as executor:
    #                     tool_result = await loop.run_in_executor(
    #                         executor,
    #                         lambda: tool_func(**arguments) if tool_func else f"未知的工具：{tool_name}"
    #                     )
    #
    #             tool_results.append({
    #                 "role": "tool",
    #                 "tool_call_id": tool_call["id"],
    #                 "content": str(tool_result),
    #                 "name": tool_name
    #             })
    #
    #         current_messages.extend(tool_results)
    #
    #     return current_messages[-1].get("content", "达到最大迭代次数"), current_messages
