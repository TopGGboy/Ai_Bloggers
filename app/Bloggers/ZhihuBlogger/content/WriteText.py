import json
import os

from app.core.AiAgent.llm import extract_json_between_markers
from app.Bloggers.BaseWriteText import BaseWriteText
from app.core.PromptManager import get_prompt_manager
from app.core.ContentPieline.ContentPipeline import create_pipeline
from app.core.config_manager import config


class WriteZhihuText(BaseWriteText):
    def __init__(self, pipeline_type: str = "simple", **pipeline_kwargs):
        """
        初始化知乎文章写作器

        Args:
            pipeline_type: 流水线类型 ("simple" 或 "enhanced")
            **pipeline_kwargs: 传递给流水线的额外参数
                - enable_enrichment: 是否启用信息增强
                - enable_quality_check: 是否启用质检
                - quality_threshold: 质量阈值
                - max_optimization_rounds: 最大优化轮数
        """
        super().__init__(platform_name="zhihu")

        # 提示词管理器
        self.prompt_mgr = get_prompt_manager()
        self.pipeline_type = pipeline_type
        self.pipeline_kwargs = pipeline_kwargs
        self.log.info(f"📦 使用内容流水线: {pipeline_type}, 配置: {pipeline_kwargs}")

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

        pipeline = create_pipeline(
            self.pipeline_type,
            platform_name="zhihu",
            **self.pipeline_kwargs
        )

        content, msg_history = await pipeline.generate(
            user_prompt=user_prompt,
            system_prompt=answer_prompt.content,
            hot_title=hot_title,
            hot_content=hot_content,
            title=hot_title
        )

        parsed_content = extract_json_between_markers(content) if isinstance(content, str) else content

        return parsed_content, msg_history

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
