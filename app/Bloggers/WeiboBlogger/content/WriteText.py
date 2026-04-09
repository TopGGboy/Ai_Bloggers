import json
import os

from app.core.AiAgent.llm import LLM, extract_json_between_markers
from app.core.MCP import MCPIntegration
from app.Bloggers.BaseWriteText import BaseWriteText

SYSTEM_PROMPT = """
# 微博头条博主创作提示词（精简版）
## 核心人设
以普通网友视角创作，接地气、有态度、不刻意，具备网感与话题敏感度，内容有情绪、观点、记忆点；适配微博轻阅读、强互动、重话题的氛围，语言网感不低俗，无AI模板感与说教感。

## 核心基调
轻量吸睛、有料易互动，兼顾传播性与真实感；短句为主、节奏明快，情绪适度不极端，快速传递核心观点，引导互动转发。

## 创作核心
产出有网感、有态度、易传播的头条文章，做到吸睛快、共鸣强、易互动；以热点为切入点，原创解读不搬运洗稿；语言口语化与网感平衡，观点鲜明，保留个人特色。

## 信息核实
涉及事实、数据、热点背景等不确定内容，调用`get_internet_data`查询最新信息；消化后自然融入行文，不复制堆砌，始终保持个人态度与网感。

## 具体创作要求
1. **标题**：15-30字，选观点/热点/情绪/反问型，不标题党，抓眼球且贴合正文
2. **开篇**：1-2行直入主题，热点/情绪/观点三选一切入，快速抓注意力
3. **正文**：短句为主，每段1-3行，可用1-5字轻小标题；仅加粗1处核心，适度用语气词，自然融入互动问句
4. **观点**：立足网友视角，直白落地有态度，不偏激、不空洞，有共鸣与记忆点
5. **结尾**：1-2句总结观点+口语化互动引导，搭配2-3个话题标签，不强行升华
6. **篇幅**：常规300-600字，深度解读700-1000字，多分段保阅读节奏

## 避坑提醒
- 原创表达，拒绝洗稿套模板，保留真人感
- 标题不浮夸误导，不滥用极端博眼球词汇
- 观点真诚不极端，不堆砌信息、不晦涩
- 内容正向不低俗，不盲目跟风造谣
- 网络搜索仅为信息辅助，核心为个人原创解读

## 输出要求
按以下JSON格式输出，字段内容采用markdown格式
```json
{
    "title": "标题",
    "summary": "导语",
    "content": "正文"
}
```
"""


class WriteWeiboText(BaseWriteText):
    def __init__(self, model_name="deepseek-chat"):
        """
        初始化微博文章写作器

        Args:
            model_name (str): 使用的大模型名称，默认为 deepseek-chat
        """
        super().__init__(platform_name="weibo")
        self.model_name = model_name
        self.llm = LLM()
        self.client = self.llm.create_async_client(model_name)  # 用于异步生成
        self.mcp_integration = MCPIntegration()

    async def write_hot_text_async(self, hot_title: str, hot_text_content: list, question_head: str):
        """
        异步版本：根据热点话题创作知乎文章

        Args:
            hot_title (str): 热点话题标题
            hot_text_content (list): 热点话题详细内容
            question_head (str): 热点话题问题简介

        Returns:
            tuple: (生成的文章内容，消息历史记录)
        """
        hot_contents = ""
        for index, content in enumerate(hot_text_content):
            hot_contents += f"\n===\n第{index + 1}篇:\n {content}\n"

        user_prompt = f"""\
        请基于以下热点信息创作一篇高质量的微博文章：

        热点标题：{hot_title}
        热点内容：{hot_contents}
        问题简介：{question_head}
        """

        content, new_msg_history = await self.mcp_integration.chat_with_tools_async(
            user_prompt=user_prompt,
            client=self.client,
            model=self.model_name,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.7
        )

        # 解析json
        content = extract_json_between_markers(content)

        return content, new_msg_history


if __name__ == '__main__':
    import asyncio


    async def main():
        write_text = WriteWeiboText()
        content, new_msg_history = await write_text.write_hot_text_async("梅姨被逮捕", ["梅姨被逮捕", "梅姨被逮捕"], "")
        print(content)


    asyncio.run(main())
