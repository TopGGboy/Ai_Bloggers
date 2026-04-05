import openai
import re
import json
from typing import Any, List, Dict, Tuple
from app.tools.LoggingConfig import LoggingConfig
from app.core.config_manager import config  # 使用新的配置管理器

MAX_NUM_TOKENS = 8192  # 生成响应的最大token数量， 8k

ALL_MODELS = [
    # deepseek模型
    "deepseek-chat",
    "deepseek-reasoning"
]


class LLM:
    def __init__(self):
        # 使用 YAML 配置的日志路径
        self.log = LoggingConfig(log_file_path=config.logfile_path, log_level=config.log_level).get_logger(
            self.__class__.__name__)

    def create_client(self, model: str):
        """
        根据指定的模型名称创建对应大模型客户端。

        Args:
            model (str): 大模型名称

        Returns:
            初始化后大模型客户端对象

        Raises:
            ValueError: 如果指定的模型名称无效
        """
        if "deepseek" in model:
            # 获取 DeepSeek 配置
            deepseek_config = config.get_deepseek_config()
            api_key = deepseek_config.get('api_key', '')

            # 验证 API 密钥是否存在
            if not api_key or api_key == "<KEY>":
                self.log.error("DeepSeek API 密钥未配置")
                raise ValueError("请在配置文件中设置有效的 DeepSeek API 密钥")

            self.log.info(f"使用的模型：{model}")

            # 创建 DeepSeek 客户端
            client = openai.OpenAI(
                api_key=api_key,
                base_url=deepseek_config.get('base_url', 'https://api.deepseek.com')
            )

            return client

    def create_async_client(self, model: str):
        """
        创建异步客户端

        Args:
            model (str): 大模型名称

        Returns:
            异步大模型客户端对象
        """
        if "deepseek" in model:
            deepseek_config = config.get_deepseek_config()
            api_key = deepseek_config.get('api_key', '')

            if not api_key or api_key == "<KEY>":
                self.log.error("DeepSeek API 密钥未配置")
                raise ValueError("请在配置文件中设置有效的 DeepSeek API 密钥")

            self.log.info(f"使用的异步模型：{model}")

            # 【关键修改】使用 AsyncOpenAI 客户端
            client = openai.AsyncOpenAI(
                api_key=api_key,
                base_url=deepseek_config.get('base_url', 'https://api.deepseek.com')
            )

            return client

    def get_response_from_llm(
            self,
            user_prompt: str | None,
            client: Any,
            model: str,
            system_prompt: str,
            print_debug: bool = False,
            msg_history: list[dict[str, Any]] | None = None,
            temperature: float = 0.7,
            tools: list[dict] | None = None,  # 添加tools参数
    ) -> tuple[str, list[dict[str, Any]]]:
        """
        调用大模型API获取响应内容。

        Args:
            user_prompt (str): 用户输入的提示词或问题
            client (Any): 大模型客户端对象，由create_client函数创建
            model (str): 大模型名称
            system_prompt (str): 系统消息，用于设定AI助手的角色和行为
            print_debug (bool, optional): 是否打印调试信息，包括完整的消息历史。默认为False
            msg_history (list[dict[str, Any]] | None, optional): 历史对话消息列表，每条消息包含role和content字段。默认为None
            temperature (float, optional): 生成温度参数，范围0-1，值越高生成越随机。默认为0.7
            tools (List[Dict] | None, optional): 可用工具列表，符合OpenAI工具格式。默认为None

        Returns:
            tuple[str, list[dict[str, Any]]]: 返回一个元组，包含：
                - 第一个元素：大模型生成的响应内容字符串
                - 第二个元素：更新后的消息历史列表

        Raises:
            ValueError: 当传入的模型名称不在支持列表中时抛出
            openai.RateLimitError: API调用速率限制错误（会自动重试）
            openai.APITimeoutError: API调用超时错误（会自动重试）
            openai.InternalServerError: API内部服务器错误（会自动重试）

        Note:
            - 该函数使用@backoff装饰器，在遇到特定错误时会自动进行指数退避重试
            - 最大生成token数量由MAX_NUM_TOKENS常量控制
            - 不同模型平台的调用方式略有差异，函数内部会自动处理
        """
        content = None
        msg = user_prompt
        if msg_history is None:
            msg_history = []

        # 避免在工具调用迭代中添加空的用户消息
        if msg and msg.strip():  # 只有当用户消息不为空且不是None时才添加
            new_msg_history = msg_history + [{"role": "user", "content": msg}]
        else:
            new_msg_history = msg_history  # 直接使用历史消息，不添加空用户消息

        try:
            if "deepseek" in model:
                api_params = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},  # 修复：统一使用system_prompt变量名
                        *new_msg_history,
                    ],
                    "temperature": temperature,
                    "max_tokens": MAX_NUM_TOKENS,
                    "n": 1,
                }

                if tools:
                    api_params["tools"] = tools

                response = client.chat.completions.create(**api_params)
                content = response.choices[0].message.content
                new_msg_history = new_msg_history + [{"role": "assistant", "content": content}]

                # 修改后：
                if hasattr(response.choices[0].message, 'tool_calls') and response.choices[0].message.tool_calls:
                    new_msg_history[-1]["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in response.choices[0].message.tool_calls
                    ]

        except Exception as e:
            self.log.error(f"调用大模型API时出错：{e}")
            raise e

        return content, new_msg_history

    async def get_response_from_llm_async(
            self,
            user_prompt: str | None,
            client: Any,
            model: str,
            system_prompt: str,
            print_debug: bool = False,
            msg_history: list[dict[str, Any]] | None = None,
            temperature: float = 0.7,
            tools: list[dict] | None = None,
            max_retries: int = 3,
    ):
        """
        异步版本：调用大模型 API 获取响应内容（流式输出）
        """
        import time

        content = None
        msg = user_prompt
        if msg_history is None:
            msg_history = []

        if msg and msg.strip():
            new_msg_history = msg_history + [{"role": "user", "content": msg}]
        else:
            new_msg_history = msg_history

        # 构建请求参数（重试时复用）
        if "deepseek" in model:
            api_params = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    *new_msg_history,
                ],
                "temperature": temperature,
                "max_tokens": MAX_NUM_TOKENS,
                "n": 1,
                "stream": True,
            }

            if tools:
                api_params["tools"] = tools

        last_error = None
        for attempt in range(max_retries):
            try:
                self.log.debug(
                    f"[LLM] 流式请求开始 (第{attempt + 1}/{max_retries}次)，消息数: {len(new_msg_history)}，has_tools: {tools is not None}")

                # 流式接收
                content_parts = []
                tool_calls_chunks = {}

                async with await client.chat.completions.create(**api_params) as response:
                    async for chunk in response:
                        if not chunk.choices:
                            continue
                        delta = chunk.choices[0].delta

                        if delta.content:
                            content_parts.append(delta.content)

                        if delta.tool_calls:
                            for tc in delta.tool_calls:
                                idx = tc.index
                                if idx not in tool_calls_chunks:
                                    tool_calls_chunks[idx] = {"id": "", "type": "function",
                                                              "function": {"name": "", "arguments": ""}}
                                if tc.id:
                                    tool_calls_chunks[idx]["id"] = tc.id
                                if tc.type:
                                    tool_calls_chunks[idx]["type"] = tc.type
                                if tc.function:
                                    if tc.function.name:
                                        tool_calls_chunks[idx]["function"]["name"] += tc.function.name
                                    if tc.function.arguments:
                                        tool_calls_chunks[idx]["function"]["arguments"] += tc.function.arguments

                content = "".join(content_parts) if content_parts else None

                # 组装 assistant 消息
                assistant_msg = {"role": "assistant", "content": content}

                if tool_calls_chunks:
                    tool_names = [tool_calls_chunks[i]["function"]["name"] for i in sorted(tool_calls_chunks)]
                    self.log.info(f"[LLM] 收到 tool_calls: {tool_names}")
                    assistant_msg["tool_calls"] = [tool_calls_chunks[i] for i in sorted(tool_calls_chunks)]
                else:
                    self.log.info(f"[LLM] 收到文本回复，长度: {len(content) if content else 0}")

                new_msg_history = new_msg_history + [assistant_msg]
                return content, new_msg_history  # 成功则直接返回

            except (openai.APIConnectionError, openai.APITimeoutError) as e:
                last_error = e
                retry_count = max_retries - attempt - 1
                if retry_count > 0:
                    wait_time = 2 ** attempt + 1  # 1s, 3s, 7s
                    self.log.warning(f"[LLM] 连接错误: {e}，{wait_time}秒后重试 (剩余{retry_count}次)")
                    await asyncio.sleep(wait_time)
                else:
                    self.log.error(f"[LLM] 达到最大重试次数 {max_retries}，放弃")

            except Exception as e:
                self.log.error(f"[LLM] 调用大模型 API 时出错：{e}")
                raise e

        # 所有重试都失败
        raise last_error

    # async def get_response_from_llm_async(
    #         self,
    #         user_prompt: str | None,
    #         client: Any,
    #         model: str,
    #         system_prompt: str,
    #         print_debug: bool = False,
    #         msg_history: list[dict[str, Any]] | None = None,
    #         temperature: float = 0.7,
    #         tools: list[dict] | None = None,
    # ) -> tuple[str, list[dict[str, Any]]]:
    #     """
    #     异步版本：调用大模型 API 获取响应内容
    #     """
    #     content = None
    #     msg = user_prompt
    #     if msg_history is None:
    #         msg_history = []
    #
    #     if msg and msg.strip():
    #         new_msg_history = msg_history + [{"role": "user", "content": msg}]
    #     else:
    #         new_msg_history = msg_history
    #
    #     try:
    #         if "deepseek" in model:
    #             api_params = {
    #                 "model": model,
    #                 "messages": [
    #                     {"role": "system", "content": system_prompt},
    #                     *new_msg_history,
    #                 ],
    #                 "temperature": temperature,
    #                 "max_tokens": MAX_NUM_TOKENS,
    #                 "n": 1,
    #             }
    #
    #             if tools:
    #                 api_params["tools"] = tools
    #
    #             # 【关键修改】使用异步 API 调用 + 超时控制
    #             self.log.debug(f"[LLM] 异步请求开始，消息数: {len(new_msg_history)}，has_tools: {tools is not None}")
    #             response = await client.chat.completions.create(**api_params)
    #             content = response.choices[0].message.content
    #             new_msg_history = new_msg_history + [{"role": "assistant", "content": content}]
    #
    #             # 修改后：
    #             if hasattr(response.choices[0].message, 'tool_calls') and response.choices[0].message.tool_calls:
    #                 tool_names = [tc.function.name for tc in response.choices[0].message.tool_calls]
    #                 self.log.info(f"[LLM] 收到 tool_calls: {tool_names}")
    #                 new_msg_history[-1]["tool_calls"] = [
    #                     {
    #                         "id": tc.id,
    #                         "type": tc.type,
    #                         "function": {
    #                             "name": tc.function.name,
    #                             "arguments": tc.function.arguments
    #                         }
    #                     }
    #                     for tc in response.choices[0].message.tool_calls
    #                 ]
    #             else:
    #                 self.log.info(f"[LLM] 收到文本回复，长度: {len(content) if content else 0}")
    #
    #     except Exception as e:
    #         self.log.error(f"调用大模型 API 时出错：{e}")
    #         raise e
    #
    #     return content, new_msg_history


def extract_json_between_markers(llm_output: str) -> dict | None:
    """
    从大模型输出中提取并解析JSON内容。（仅提取匹配的第一个JSON块）

    该函数尝试从LLM的输出文本中提取JSON数据，支持多种格式：
    1. 首先尝试提取Markdown代码块中的JSON（```json ... ```）
    2. 如果失败，尝试提取任何花括号包裹的内容
    3. 对于解析失败的JSON，尝试清理控制字符后重新解析

    Args:
        llm_output (str): 大模型的输出文本，可能包含JSON内容

    Returns:
        dict | None: 成功解析返回字典对象，失败返回None

    Note:
        - 函数会按顺序尝试所有匹配的JSON字符串，返回第一个成功解析的结果
        - 使用re.DOTALL模式以支持多行JSON内容
        - 自动清理无效的控制字符（\\x00-\\x1F, \\x7F）
    """
    if llm_output is None:
        return None
    # 在```json和```之间查找JSON内容的正则表达式模式
    json_pattern = r"```json(.*?)```"
    matches = re.findall(json_pattern, llm_output,
                         re.DOTALL)  # 在llm_output中查找所有匹配json_pattern的内容。re.DOTALL表示点号匹配包括换行符在内的所有字符。

    if not matches:
        # 如果没有找到匹配的JSON内容，则尝试在输出中查找任何JSON-like内容
        json_pattern = r"\{.*?\}"
        matches = re.findall(json_pattern, llm_output, re.DOTALL)

    for json_string in matches:
        json_string = json_string.strip()
        try:
            parsed_json = json.loads(json_string)
            return parsed_json
        except json.JSONDecodeError:
            # 尝试修复常见的JSON问题
            try:
                # 移除无效的控制字符
                json_string_clean = re.sub(r"[\x00-\x1F\x7F]", "", json_string)
                parsed_json = json.loads(json_string_clean)
                return parsed_json
            except json.JSONDecodeError:
                continue  # 尝试下一个匹配

    return None  # 没有找到有效的JSON


if __name__ == '__main__':
    import asyncio


    async def main():
        llm = LLM()
        # 使用异步客户端
        client = llm.create_async_client("deepseek-chat")
        content, new_msg_history = await llm.get_response_from_llm_async(
            user_prompt="你好",
            client=client,
            model="deepseek-chat",
            system_prompt="你是一个有用的AI助手，可以帮助用户解决各种问题。",
            temperature=0.7
        )
        print(content)
        print(new_msg_history)


    # 运行异步主函数
    asyncio.run(main())
