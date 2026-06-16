"""
全局 pytest 夹具和配置
"""
import pytest


@pytest.fixture
def sample_article_text() -> str:
    """一篇示例文章，供多个测试复用"""
    return """
    最近人工智能的发展速度让人瞠目结舌。从 ChatGPT 到 GPT-4，再到各种垂直领域的 AI 应用，
    技术的迭代周期已经从年缩短到了月。

    很多人担心 AI 会取代人类的工作。但我认为，与其焦虑不如拥抱变化。
    关键在于如何利用 AI 提升自己的生产效率。

    以内容创作为例，AI 可以帮助我们：
    1. 快速生成初稿
    2. 优化表达方式
    3. 多语言翻译
    4. 数据分析支撑

    但最终的核心创意和情感表达，仍然需要人类的参与。
    AI 是工具，不是替代品。
    """


@pytest.fixture
def sample_platform_data() -> dict:
    """模拟的平台数据"""
    return {
        "content_meta": {
            "is_video_answer": 0,
            "thumbnail": "https://pic.zhihu.com/test.jpg",
            "excerpt": "这是一段摘要 <img src='pic.jpg'> 内容",
        },
        "stats": {
            "likes": 1523,
            "comments": 89,
            "shares": 45,
        }
    }
