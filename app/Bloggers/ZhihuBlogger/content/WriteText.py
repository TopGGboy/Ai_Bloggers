import json
import os

from app.core.AiAgent.llm import LLM, extract_json_between_markers
from app.core.MCP import MCPIntegration
from app.Bloggers.BaseWriteText import BaseWriteText
from app.core.PromptManager import get_prompt_manager
from app.core.config_manager import config


class WriteZhihuText(BaseWriteText):
    def __init__(self):
        """
        初始化知乎文章写作器
        """
        super().__init__(platform_name="zhihu")

        self.llm = LLM()
        self.client = self.llm.create_async_client(self.model_name)
        self.async_client = self.llm.create_async_client(self.model_name)  # 用于异步生成
        self.mcp_integration = MCPIntegration(client=self.client, model_name=self.model_name, platform_name="zhihu",
                                              platform_config=config.platforms["zhihu"])

        # 提示词管理器
        self.prompt_mgr = get_prompt_manager()

    async def write_hot_answer_async(self, hot_title: str, hot_content: list, question_head: str):
        """
        异步版本：根据热点话题创作知乎回答

        Args:
            hot_title (str): 热点话题标题
            hot_content (list): 热点话题详细内容
            question_head (str): 热点话题问题简介
        """
        hot_contents = ""
        for index, content in enumerate(hot_content):
            hot_contents += f"\n===\n第{index + 1}篇:\n {content}\n"

        user_prompt = f"""
        请基于以下热点信息创作一篇高质量的知乎文章：

        热点标题：{hot_title}
        热点内容：{hot_content}
        问题简介：{question_head}
        """

        # 从 PromptManager 获取系统提示词
        answer_prompt = self.prompt_mgr.get_prompt("zhihu_answer")

        content, new_msg_history = await self.mcp_integration.chat_with_tools_async(
            user_prompt=user_prompt,
            client=self.async_client,
            model=self.model_name,
            system_prompt=answer_prompt.content,
            temperature=self.temperature
        )

        content = extract_json_between_markers(content)

        return content, new_msg_history

    async def write_hot_article_async(self, hot_title: str, hot_content: list, question_head: str) -> tuple[str, list]:
        """
        异步版本：根据热点话题创作文章

        :param hot_title: 热点话题标题
        :param hot_content: 热点话题详细内容
        :param question_head: 热点话题问题简介
        :return: content, new_msg_history
        """
        pass


if __name__ == '__main__':
    import asyncio


    async def main():
        write_text = WriteZhihuText()
        content, new_msg_history = await write_text.write_hot_answer_async(
            "男子从内地偷运 51 公斤盒饭回澳门，被海关查获，为啥要专门偷运盒饭？未经检疫的熟食入境会有什么风险？", ["", ""],
            "")
        print(content)


    asyncio.run(main())
