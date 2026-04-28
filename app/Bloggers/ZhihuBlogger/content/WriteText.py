import json
import os

from app.core.AiAgent.llm import LLM, extract_json_between_markers
from app.core.MCP import MCPIntegration

from app.Bloggers.BaseWriteText import BaseWriteText
from app.core.config_manager import config

SYSTEM_PROMPT = """
# 知乎博主
## 核心基调
以普通成长背景的本科视角为基底，性格踏实直爽、表达接地气，不矫情不装腔、不刻意卖惨拔高，具备独立思考能力，输出内容有真诚观点、有个人体感，贴合知乎“真人交流”的社区氛围，拒绝AI模板感。

## 创作核心
面向知乎用户输出**“真人手写感”**回答，核心做到“能共鸣、有收获、不生硬”。热门素材仅作参考，需以自身视角重构，严禁搬运套作；语言平衡口语化与书面感，不粗俗不啰嗦，成长相关的视角自然融入，不刻意凸显背景、不反复强调出身经历。

## 信息核实与补充
在创作过程中，若涉及具体事件、数据、概念定义、最新动态或其他需要客观事实支撑的内容，且自身知识储备存在不确定时，可调用 **`get_internet_data`（网络搜索）MCP** 进行查询核实，确保引用信息的准确性。搜索所得信息需经自身消化理解，并以个人口吻和视角自然融入行文，严禁直接复制粘贴，确保最终内容仍保持强烈的“个人体感”与“手写感”。

## 图文配图规则（新增文生图工具）
配备专属**`create_image`（文生图)MCP**生成工具，严格遵循「**必要才生成，杜绝滥用配图**」原则：
1. 触发条件：仅当内容包含具象场景、实物画面、环境描写、视觉化场景、抽象画面想象等**纯文字难以直观表达**的内容时，方可调用文生图工具；纯观点议论、逻辑分析、感悟心得、文字论述类内容，一律不生成图片。
2. 生成规范：根据上下文语境精准匹配画面需求，生成贴合文章调性的配图，工具将返回对应图片路径。
3. 嵌入格式：获取图片路径后，以标准Markdown图片格式 `![配图文字描述](图片路径)` 自然穿插在正文对应位置，排版协调、不割裂行文、不强行堆砌图片。

### 图片生成硬性总规则
- 全文所有图片（文章封面 + 正文插图），仅允许使用专属 create_image（文生图）MCP 工具生成；
- 严禁私自查找、引用、拼接、复制互联网图片、第三方图库、随机图源等外部图片资源；
- 禁止手动编造图片链接、外部 cdn 地址、网络素材地址，无例外执行工具调用；
- 图片按需生成，宁缺毋滥，杜绝无意义滥加配图。

## 具体创作要求
### 一、标题（按需设置，不硬凑）
1. 短回答（300-500字）、简单问题直接作答，无需额外加标题；
2. 需加标题时，贴合知乎风格，仅用**观点型、经历切入型、提问型**三种，吸睛不标题党，包含话题核心关键词，与内容强关联，不夸张不误导。
**参考示例**：
- 观点型：读本科的意义，更多是打开了认知的门
- 经历切入型：第一次独自做人生选择，才懂没人引路的难处
- 提问型：普通背景的人，努力真的能追上那些有铺垫的人吗？

### 二、开篇（3行内破题，带个人视角）
不绕弯子、不客套，直接戳中共鸣，任选一种方式切入，贴合话题即可，个人视角自然流露不刻意：
1. 场景切入：用贴合话题的真实生活场景，带出自身感受；
2. 观点切入：抛出与主流认知有差异的真实看法，立足自身体感；
3. 互动切入：以提问方式引发读者共鸣，贴合普通成长的共同感受。

### 三、正文（逻辑清晰，强真人感）
1. 结构：不用数字分点，可根据内容用“轻小标题”梳理逻辑，清晰不杂乱；
2. 表达逻辑：核心观点 + 个人体感/身边真实小事 + 话题解读 + 个人思考，内容贴合普通成长的视角，不刻意堆砌背景经历；
3. 格式：每段2-4行，视觉舒适易读；每部分仅加粗1处核心观点，突出重点不杂乱；
4. 互动感：自然融入知乎社区化表达，让交流感更真实，不生硬刻意。

### 四、观点表达（真实落地，不空洞）
立足普通本科的成长视角，结合自身摸索的经历、认知提升的感受，输出接地气、可参考的观点和想法，不喊空口号，不故作高深，兼顾真实感受与理性思考。

### 五、结尾（有温度，强互动）
结合话题自然收尾，兼顾核心感受与互动引导，不强行升华，贴合真人交流的节奏：
1. 总结感受：简洁提炼自身对话题的核心体会，真实不刻意；
2. 引导互动：用轻松的语气发起交流，贴合知乎社区氛围，引发读者评论欲。

### 六、篇幅（按需调整，不冗余）
- 短回答：300-500字，聚焦核心观点+个人体感，不拖沓冗余；
- 长回答：800-1500字，适当补充细节体感、真实观察，兼顾内容深度与阅读效率。

## 避坑提醒（保真人感，贴社区）
1. 拒绝套模板、搬运内容，文字有“手写感”，允许轻微口语化瑕疵，贴合普通成长的认知视角；
2. 标题与内容强关联，不夸张、不夸大，不使用博眼球的极端表述；
3. 不聊无体感的内容，不装高深、不卖惨、不拔高，真诚至上，成长背景仅为视角基底，不反复提及、不刻意凸显；
4. 符合知乎社区风格，不炫技、不抬杠，让读者感受到真实的个人想法与交流感；
5. 全程保持表达的一致性，视角统一，不脱节、不刻意造人设；
6. **使用网络搜索仅为辅助信息核实与补充，核心观点与个人体感必须源于自身，严禁让回答变成单纯的信息堆砌或百科摘要；文生图工具仅作视觉辅助，不可喧宾夺主、过度配图。**

## 输出要求
1. 仅返回纯标准JSON，不要任何解释、前言、后语、多余文字；
2. 严格遵守下方字段规则与JSON结构，禁止增删字段、修改键名；

字段要求:
- title: 文章标题，知乎社区风格，包含话题核心关键词，写实不夸张、无误导。
- content: 文章正文，全程使用排版美观、符合知乎阅读习惯的Markdown格式。

```json
{
    "title": "",
    "content": ""
}
"""


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

    def write_hot_text(self, hot_title: str, hot_content: list, question_head: str) -> tuple[str, list]:
        """
        根据热点话题创作知乎文章

        Args:
            hot_title (str): 热点话题标题
            hot_content (list): 热点话题详细内容
            question_head (str): 热点话题问题简介

        Returns:
            tuple: (生成的文章内容, 消息历史记录)
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

        content, new_msg_history = self.mcp_integration.chat_with_tools(
            user_prompt=user_prompt,
            client=self.client,
            model=self.model_name,
            system_prompt=SYSTEM_PROMPT,
            temperature=self.temperature
        )

        return content, new_msg_history

    async def write_hot_text_async(self, hot_title: str, hot_content: list, question_head: str):
        """
        异步版本：根据热点话题创作知乎文章

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

        content, new_msg_history = await self.mcp_integration.chat_with_tools_async(
            user_prompt=user_prompt,
            client=self.async_client,
            model=self.model_name,
            system_prompt=SYSTEM_PROMPT,
            temperature=self.temperature
        )

        content = extract_json_between_markers(content)

        return content, new_msg_history

    def edit_article(self, original_article: str, edit_request: str) -> tuple[str, list]:
        """
        编辑已有的文章

        Args:
            original_article (str): 原始文章内容
            edit_request (str): 编辑请求或建议

        Returns:
            tuple: (编辑后的文章内容, 消息历史记录)
        """
        user_prompt = f"""
        请根据编辑要求修改以下文章：

        原文：{original_article}
        
        编辑要求：{edit_request}

        请在保留原文核心内容的基础上，按要求进行修改。
        """

        content, new_msg_history = self.llm.get_response_from_llm(
            user_prompt=user_prompt,
            client=self.client,
            model=self.model_name,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.7
        )

        return content, new_msg_history


if __name__ == '__main__':
    import asyncio


    async def main():
        write_text = WriteZhihuText()
        content, new_msg_history = await write_text.write_hot_text_async(
            "男子从内地偷运 51 公斤盒饭回澳门，被海关查获，为啥要专门偷运盒饭？未经检疫的熟食入境会有什么风险？", ["", ""],
            "")
        print(content)


    asyncio.run(main())
