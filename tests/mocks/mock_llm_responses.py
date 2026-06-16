"""
模拟 LLM 响应，用于测试依赖 AI 的模块
"""
import json

MOCK_CONTENT_ANALYSIS_RESPONSE = {
    "score": 8.5,
    "passed": True,
    "comments": ["信息密度高", "观点独特"],
    "suggestions": ["可以增加更多案例"],
    "confidence": 0.9,
}

MOCK_HOOK_ANALYSIS_RESPONSE = {
    "score": 7.0,
    "passed": True,
    "comments": ["标题有吸引力"],
    "suggestions": ["开篇可以更抓人"],
    "confidence": 0.8,
}

MOCK_STRUCTURE_RESPONSE = {
    "score": 8.0,
    "passed": True,
    "comments": ["逻辑清晰", "段落节奏好"],
    "suggestions": ["结尾可以更强有力"],
    "confidence": 0.85,
}

MOCK_PLATFORM_FIT_RESPONSE = {
    "score": 7.5,
    "passed": True,
    "comments": ["符合平台调性"],
    "suggestions": ["可以增加互动引导"],
    "confidence": 0.8,
}


def create_mock_llm_response(content: dict) -> str:
    """将字典包装为 LLM 返回的文本格式（含 ```json 标记）"""
    return f"```json\n{json.dumps(content, ensure_ascii=False)}\n```"
