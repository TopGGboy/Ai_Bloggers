"""
测试 NLP 内容特征分析器



注意：此模块在 jieba/snownlp 缺失时会自动降级，
所以测试在无第三方 NLP 库的环境下也能通过。
"""
import pytest
from app.core.learning_system.content_analyzer import ContentAnalyzer


class TestContentAnalyzer:
    """ContentAnalyzer 纯逻辑测试"""

    @pytest.fixture
    def analyzer(self):
        return ContentAnalyzer()

    # ── 文本清理 ────────────────────────────────
    def test_clean_text_removes_html(self, analyzer):
        dirty = "<p>这是一段正文</p><br/>还有<a>链接</a>"
        assert analyzer.clean_text(dirty) == "这是一段正文还有链接"

    def test_clean_text_removes_links(self, analyzer):
        text = "详情请见 https://example.com/article 或 http://short.url"
        result = analyzer.clean_text(text)
        assert "https://" not in result
        assert "http://" not in result

    def test_clean_text_combined(self, analyzer):
        text = '<p>Hello @world! Visit https://test.com</p>'
        assert analyzer.clean_text(text) == "Hello ! Visit"

    # ── 提取功能 ────────────────────────────────

    def test_extract_mentions(self, analyzer):
        text = "@张三 和 @李四_123 都来了，@王五"
        assert analyzer.extract_mentions(text) == ["张三", "李四_123", "王五"]

    def test_extract_links(self, analyzer):
        text = "看这里 https://example.com 和 http://test.org/path"
        links = analyzer.extract_links(text)
        assert "https://example.com" in links
        assert "http://test.org/path" in links

    def test_extract_hashtags(self, analyzer):
        text = "今天讨论#人工智能#和#深度学习#的话题"
        assert analyzer.extract_hashtags(text) == ["人工智能", "深度学习"]

    # ── 表层文本特征 ────────────────────────────

    def test_surface_text_basic(self, analyzer):
        result = analyzer.analyze_surface_text(
            title="测试标题",
            excerpt="这是正文内容。有两句话。"
        )
        assert result["char_count"] > 0
        assert result["sentence_count"] == 2
        assert result["has_mention"] is False
        assert result["has_link"] is False

    def test_surface_text_with_mention_and_link(self, analyzer):
        result = analyzer.analyze_surface_text(
            title="测试",
            excerpt="@某人 请看 https://example.com"
        )
        assert result["has_mention"] is True
        assert result["mention_count"] == 1
        assert result["has_link"] is True
        assert result["link_domain"] == "example.com"

    def test_surface_text_empty(self, analyzer):
        result = analyzer.analyze_surface_text(title="", excerpt="")
        assert result["char_count"] == 0
        assert result["sentence_count"] == 0
        assert result["paragraph_breaks"] == 0

    def test_surface_text_paragraph_breaks(self, analyzer):
        result = analyzer.analyze_surface_text(
            title="标题",
            excerpt="第一行\n第二行\n\n第四行"
        )
        assert result["paragraph_breaks"] == 3

    # ── 语言风格 ────────────────────────────────

    def test_language_style_avg_sentence_length(self, analyzer):
        text = "短句。也很短。第三句。"
        result = analyzer.analyze_language_style(text)
        assert result["avg_sentence_length"] > 0

    def test_language_style_emoji_count(self, analyzer):
        text = "Happy😊 Go💪💪"
        result = analyzer.analyze_language_style(text)
        assert result["emoji_count"] == 3

    def test_language_style_bracket_aside(self, analyzer):
        text_with = "深度学习（一种机器学习方法）很重要"
        text_without = "深度学习很重要"
        result_with = analyzer.analyze_language_style(text_with)
        result_without = analyzer.analyze_language_style(text_without)
        assert result_with["has_bracket_aside"] is True
        assert result_without["has_bracket_aside"] is False

    def test_language_style_empty_text(self, analyzer):
        result = analyzer.analyze_language_style("")
        assert result["avg_sentence_length"] == 0.0
        assert result["sentiment_polarity"] == 0.0
        assert result["emoji_count"] == 0

    # ── 多媒体分析 ────────────────────────────────

    @pytest.mark.parametrize("platform_data,expected_type", [
        ({"content_meta": {"is_video_answer": 1, "duration": 120}}, "视频"),
        ({"content_meta": {"thumbnail": "http://img.com/1.jpg"}}, "图片"),
        ({"content_meta": {"excerpt": "文字内容 <img src='a.jpg'>"}}, "图片"),
        ({"content_meta": {}}, "无"),
    ])
    def test_multimedia_analysis(self, analyzer, platform_data, expected_type):
        result = analyzer.analyze_multimedia(platform_data)
        assert result["media_type"] == expected_type

    # ── 情感分析（基于词典的降级方案）────────────

    def test_sentiment_positive(self, analyzer):
        text = "太棒了！非常精彩的表现，真心喜欢，值得点赞！"
        result = analyzer.analyze_language_style(text)
        assert result["sentiment_polarity"] > 0

    def test_sentiment_negative(self, analyzer):
        text = "太差了！垃圾服务，非常失望，让人愤怒！"
        result = analyzer.analyze_language_style(text)
        assert result["sentiment_polarity"] < 0

    def test_sentiment_neutral(self, analyzer):
        text = "今天天气不错，我去超市买了些东西。"
        result = analyzer.analyze_language_style(text)
        assert -1 < result["sentiment_polarity"] < 1
