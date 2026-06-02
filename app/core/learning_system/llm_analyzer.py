"""
LLM 深层内容特征分析器

对大模型能更好理解的字段进行深度分析：
- hook_and_structure：开头钩子、整体结构、结尾 CTA
- topic_and_semantics：主题、实体、内容支柱、切入角度
- language_style 的深层部分：情感波动、术语占比
"""
import asyncio
from typing import Dict, Any, Optional

from app.core.ai_agent.llm import LLM, extract_json_between_markers

# ── 专属系统提示词 ──────────────────────────────────────────
SYSTEM_PROMPT = """
# 你是一个专业的内容分析专家。分析用户提供的文本内容，返回结构化的 JSON。

## 要求：
1. 仅输出 JSON，不包含任何解释或其他文字
2. JSON 外层必须用引号```json...```包裹
3. 严格遵守以下格式
```json
{ 
"hook_and_structure": { 
    "hook_type": "string", 
    "hook_contains_number": true, 
    "hook_emotion": "string", 
    "structure_type": "string", 
    "cta_type": "string", 
    "cta_position": "string" 
}, 
"topic_and_semantics": { 
    "primary_topic": "string",
    "sub_topic": "string", 
    "entities": [], 
    "content_pillar": "string", 
    "content_angle": "string", 
    "is_evergreen": true, 
    "is_trend_related": true, 
    "trend_name": "string or null" 
} 
}

## 字段说明：
- hook_type：开头类型 → 提问/惊人事实/痛点共鸣/反常识/悬念/直接陈述/故事引入/数据开头/引用开头
- hook_contains_number：钩子中是否包含数字
- hook_emotion：钩子传递的情绪 → 惊讶/好奇/愤怒/温暖/担忧/兴奋/悲伤/无
- structure_type：整体结构 → 清单体/故事体/观点论证/对话体/问题-方案/对比分析/案例分析/教程步骤/总分总
- cta_type：结尾号召类型 → 评论/点赞/转发/关注/点击链接/收藏/无
- cta_position：CTA 位置 → 前/中/后/无

- primary_topic：核心主题（简洁，5 字以内）
- sub_topic：子主题（可选）
- entities：提取的关键实体列表（人名、品牌、产品、事件、地点等）
- content_pillar：内容支柱 → 教育/娱乐/灵感/新闻/促销/互动提问/观点争议/案例分享
- content_angle：切入角度 → 教程/案例/观点/资源推荐/工具测评/经验分享/盘点汇总/数据分析/深度解读
- is_evergreen：是否常青内容（不依赖时效性）
- is_trend_related：是否关联热点
- trend_name：热点名称（不是热点则为 null）
"""


class LLMContentAnalyzer:
    """基于大模型的深层内容分析器"""

    def __init__(self, model: str = "deepseek-v4-flash"):
        self.llm = LLM()
        self.model = model
        self._client = None

    async def _ensure_client(self):
        if self._client is None:
            self._client = self.llm.create_async_client(self.model)

    async def analyze_deep_features(self, title: str, excerpt: str) -> Dict[str, Any]:
        """
        使用 LLM 分析深层内容特征

        :param title:     标题
        :param excerpt:   正文/摘要

        :return: 深层特征字典

        返回结构：
        {
            "hook_and_structure": {...},
            "topic_and_semantics": {...},
        }
        """
        if not title and not excerpt:
            return self._default_features()

        await self._ensure_client()

        user_prompt = f"请分析以下内容：\n\n标题：{title}\n\n正文：\n{excerpt}"

        try:
            content, _ = await self.llm.get_response_from_llm_async(
                user_prompt=user_prompt,
                client=self._client,
                model=self.model,
                system_prompt=SYSTEM_PROMPT,
                temperature=0.3,
            )

            parsed = extract_json_between_markers(content) or {}
            return {
                "hook_and_structure": parsed.get("hook_and_structure", {}),
                "topic_and_semantics": parsed.get("topic_and_semantics", {}),
            }

        except Exception:
            return self._default_features()

    # ── 默认兜底 ──────────────────────────────────────────────

    @staticmethod
    def _default_features() -> Dict[str, Any]:
        return {
            "hook_and_structure": {
                "hook_type": "直接陈述",
                "hook_contains_number": False,
                "hook_emotion": "无",
                "structure_type": "观点论证",
                "cta_type": "无",
                "cta_position": "无",
            },
            "topic_and_semantics": {
                "primary_topic": "",
                "sub_topic": "",
                "entities": [],
                "content_pillar": "教育",
                "content_angle": "观点",
                "is_evergreen": True,
                "is_trend_related": False,
                "trend_name": None,
            },
        }
