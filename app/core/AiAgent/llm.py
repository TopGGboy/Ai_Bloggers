import openai
from typing import Any, List, Dict, Tuple
from app.tools.LoggingConfig import LoggingConfig
from app.core.config_manager import config  # 使用新的配置管理器

MAX_NUM_TOKENS = 8192  # 生成响应的最大token数量，8K

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

                # 如果有工具调用，也添加到消息历史中
                if hasattr(response.choices[0].message, 'tool_calls') and response.choices[0].message.tool_calls:
                    new_msg_history[-1]["tool_calls"] = response.choices[0].message.tool_calls

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
    ) -> tuple[str, list[dict[str, Any]]]:
        """
        异步版本：调用大模型 API 获取响应内容
        """
        content = None
        msg = user_prompt
        if msg_history is None:
            msg_history = []

        if msg and msg.strip():
            new_msg_history = msg_history + [{"role": "user", "content": msg}]
        else:
            new_msg_history = msg_history

        try:
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
                }

                if tools:
                    api_params["tools"] = tools

                # 【关键修改】使用异步 API 调用
                response = await client.chat.completions.create(**api_params)
                content = response.choices[0].message.content
                new_msg_history = new_msg_history + [{"role": "assistant", "content": content}]

                if hasattr(response.choices[0].message, 'tool_calls') and response.choices[0].message.tool_calls:
                    new_msg_history[-1]["tool_calls"] = response.choices[0].message.tool_calls

        except Exception as e:
            self.log.error(f"调用大模型 API 时出错：{e}")
            raise e

        return content, new_msg_history


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
