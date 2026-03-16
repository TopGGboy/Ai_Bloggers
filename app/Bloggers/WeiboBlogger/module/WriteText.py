import json
import os

from app.core.AiAgent.llm import LLM
from app.core.MCP import MCPIntegration
from app.Bloggers.BaseWriteText import BaseWriteText

SYSTEM_PROMPT = """


"""


class WriteWeiboText(BaseWriteText):
    def __init__(self, model_name="deepseek-chat"):
        """
        初始化微博文章写作器

        Args:
            model_name (str): 使用的大模型名称，默认为 deepseek-chat
        """
        super().__init__()
        self.model_name = model_name
        self.llm = LLM()
        self.client = self.llm.create_async_client(model_name)  # 用于异步生成
        self.mcp_integration = MCPIntegration()

    async def write_hot_text_async(self, hot_title: str, hot_content: list, question_head: str) -> tuple[str, list]:
        """
        异步版本：根据热点话题创作知乎文章

        Args:
            hot_title (str): 热点话题标题
            hot_content (list): 热点话题详细内容
            question_head (str): 热点话题问题简介

        Returns:
            tuple: (生成的文章内容，消息历史记录)
        """
        hot_contents = ""
        for index, content in enumerate(hot_content):
            hot_contents += f"\n===\n第{index + 1}篇:\n {content}\n"

        user_prompt = f"""\
        请基于以下热点信息创作一篇高质量的微博文章：

        热点标题：{hot_title}
        热点内容：{hot_content}
        问题简介：{question_head}
        """

        content, new_msg_history = await self.mcp_integration.chat_with_tools_async(
            user_prompt=user_prompt,
            client=self.client,
            model=self.model_name,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.7
        )

        return content, new_msg_history
