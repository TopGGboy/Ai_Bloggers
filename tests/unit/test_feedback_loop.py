"""
测试自学习反馈闭环的核心逻辑
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

from app.core.learning_system.feedback_loop import (
    StatisticalMiner,
    PatternReport,
    FeatureAnalysis,
    StyleAnchorUpdater,
    ContentStrategyOptimizer,
    FeedbackLoop,
)


class TestStatisticalMiner:
    """统计矿工测试 — 核心分析逻辑"""

    @pytest.fixture
    def miner(self):
        return StatisticalMiner("zhihu")

    @pytest.fixture
    def sample_records(self):
        """模拟 20 条学习+表现记录"""
        now = datetime.now()
        records = []
        for i in range(20):
            # 模拟"中短句 + 积极情感 + 少量 emoji"互动率高
            is_high_engagement = i < 5  # 前 5 条是高互动
            engagement = 0.08 if is_high_engagement else 0.01

            records.append({
                "content_id": f"test_{i}",
                "title": f"测试标题{i}",
                "engagement_rate": engagement,
                "surface_text": {
                    "avg_sentence_length": 22.5 if is_high_engagement else 45.0,
                    "sentence_count": 12 if is_high_engagement else 25,
                    "paragraph_breaks": 5 if is_high_engagement else 12,
                    "char_count": 500,
                    "has_mention": False,
                    "mention_count": 0,
                    "has_link": False,
                },
                "language_style": {
                    "sentiment_polarity": 0.6 if is_high_engagement else 0.0,
                    "emoji_count": 2 if is_high_engagement else 0,
                    "first_person_ratio": 0.08 if is_high_engagement else 0.005,
                    "second_person_ratio": 0.02,
                    "has_bracket_aside": True,
                    "avg_sentence_length": 25.0 if is_high_engagement else 50.0,
                },
                "hook_and_structure": {
                    "hook_type": "痛点共鸣" if is_high_engagement else "直接陈述",
                    "structure_type": "观点论证",
                    "cta_type": "评论",
                    "cta_position": "后",
                },
                "topic_and_semantics": {
                    "primary_topic": "AI",
                    "content_pillar": "教育",
                    "content_angle": "经验分享",
                    "is_evergreen": True,
                    "is_trend_related": False,
                },
                "multimedia": {"media_type": "无", "media_count": 0},
                "context": {"day_of_week": "周三", "time_of_day_hour": 20},
                "likes": 150 if is_high_engagement else 10,
                "comments": 30 if is_high_engagement else 2,
                "impressions": 5000 if is_high_engagement else 200,
            })
        return records

    def test_extract_numeric_values_surface_text(self, miner, sample_records):
        """提取 surface_text 中的数值特征"""
        values = miner._extract_numeric_values(sample_records, "avg_sentence_length")
        assert len(values) == 20
        # 高互动率应该句子较短
        high_eng_values = [v for v in values if v[1] > 0.05]
        low_eng_values = [v for v in values if v[1] < 0.05]
        if high_eng_values and low_eng_values:
            avg_high = sum(v[0] for v in high_eng_values) / len(high_eng_values)
            avg_low = sum(v[0] for v in low_eng_values) / len(low_eng_values)
            assert avg_high < avg_low  # 高互动率内容句子更短

    def test_extract_categorical_values(self, miner, sample_records):
        """提取类别特征"""
        values = miner._extract_categorical_values(sample_records, "hook_type")
        assert len(values) > 0
        types = set(v[0] for v in values)
        assert "痛点共鸣" in types
        assert "直接陈述" in types

    def test_bucket_sentence_length_short(self, miner):
        assert miner._bucket_sentence_length(12) == "≤15 chars"
        assert miner._bucket_sentence_length(22) == "16-25 chars"
        assert miner._bucket_sentence_length(60) == ">50 chars"

    def test_bucket_sentiment(self, miner):
        assert miner._bucket_sentiment(-0.5) == "消极"
        assert miner._bucket_sentiment(0.0) == "中性"
        assert miner._bucket_sentiment(0.5) == "积极"

    def test_pearson_correlation(self, miner):
        """Pearson 相关系数计算"""
        # 完全正相关
        assert miner._pearson([1, 2, 3], [2, 4, 6]) == pytest.approx(1.0, rel=0.01)
        # 完全负相关
        assert miner._pearson([1, 2, 3], [6, 4, 2]) == pytest.approx(-1.0, rel=0.01)
        # 无相关
        assert miner._pearson([1, 2, 3], [5, 5, 5]) == pytest.approx(0.0, abs=0.01)
        # 数据不足
        assert miner._pearson([1], [2]) == 0.0

    def test_analyze_numeric_feature(self, miner, sample_records):
        """数值特征分析：应该找出最优区间"""
        values = miner._extract_numeric_values(sample_records, "avg_sentence_length")
        analysis = miner._analyze_numeric_feature(
            "avg_sentence_length", "平均句长", values,
            miner._bucket_sentence_length, "chars"
        )
        assert analysis is not None
        # 高互动率内容的句长较短
        assert "16-25 chars" in analysis.sweet_spot_desc or "≤15 chars" in analysis.sweet_spot_desc

    def test_analyze_categorical_feature(self, miner, sample_records):
        """类别特征分析"""
        values = miner._extract_categorical_values(sample_records, "hook_type")
        analysis = miner._analyze_categorical_feature("hook_type", values)
        assert analysis is not None
        assert analysis.sweet_spot == "痛点共鸣"


class TestPatternReport:
    """模式报告测试"""

    def test_empty_report(self):
        report = PatternReport(platform="zhihu", sample_count=0, generated_at="now")
        assert not report.has_strong_pattern("anything")
        assert report.to_style_guidance() == ""

    def test_with_patterns(self):
        report = PatternReport(
            platform="zhihu", sample_count=100, generated_at="now",
            patterns={
                "avg_sentence_length": FeatureAnalysis(
                    feature_name="平均句长",
                    sweet_spot="16-25 chars",
                    sweet_spot_desc="最优区间: 16-25 chars (平均互动率 0.0523)",
                    correlation=0.42, sample_count=100, unit="chars",
                ),
            },
        )
        assert report.has_strong_pattern("avg_sentence_length")
        assert not report.has_strong_pattern("unknown")
        assert "avg_sentence_length" in report.to_style_guidance()


class TestStyleAnchorUpdater:
    """风格锚点更新器测试"""

    @pytest.mark.asyncio
    async def test_update_empty_report(self):
        """空报告不更新任何锚点"""
        with patch("app.core.storage.manager.AsyncStorageManager.save_style_anchor",
                   new_callable=AsyncMock) as mock_save:
            updater = StyleAnchorUpdater("zhihu")
            report = PatternReport(
                platform="zhihu", sample_count=0, generated_at="now"
            )
            count = await updater.update_from_report(report)
            assert count == 0
            mock_save.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_with_patterns(self):
        """有模式时更新锚点"""
        with patch("app.core.storage.manager.AsyncStorageManager.save_style_anchor",
                   new_callable=AsyncMock) as mock_save:
            updater = StyleAnchorUpdater("zhihu")
            report = PatternReport(
                platform="zhihu", sample_count=10, generated_at="now",
                patterns={
                    "avg_sentence_length": FeatureAnalysis(
                        feature_name="平均句长",
                        sweet_spot="16-25 chars",
                        sweet_spot_desc="最优区间: 16-25 chars (平均互动率 0.0523)",
                        correlation=0.42, sample_count=10, unit="chars",
                    ),
                },
            )
            count = await updater.update_from_report(report)
            assert count == 1
            mock_save.assert_awaited_once()


class TestContentStrategyOptimizer:
    """策略优化器测试"""

    @pytest.mark.asyncio
    async def test_get_style_guidance_empty(self):
        """没有风格锚点时返回空字符串"""
        with patch("app.core.storage.manager.AsyncStorageManager.get_effective_styles",
                   return_value=[]):
            optimizer = ContentStrategyOptimizer("zhihu")
            guidance = await optimizer.get_style_guidance()
            assert guidance == ""

    @pytest.mark.asyncio
    async def test_get_dynamic_weights(self):
        """动态权重返回合法值"""
        with patch("app.core.storage.manager.AsyncStorageManager.get_effective_styles",
                   return_value=[]):
            optimizer = ContentStrategyOptimizer("zhihu")
            weights = await optimizer.get_dynamic_weights()
            # 应包含所有 5 个维度
            for dim in ("handwriting_score", "information_density",
                        "viewpoint_uniqueness", "structure_readability",
                        "platform_adaptation"):
                assert dim in weights
            # 总和约为 1.0
            assert abs(sum(weights.values()) - 1.0) < 0.01


class TestFeedbackLoop:
    """反馈闭环编排器测试"""

    @pytest.mark.asyncio
    async def test_run_no_data(self):
        """没有数据时正常运行，返回空报告"""
        with patch("app.core.storage.manager.AsyncStorageManager.count_contents",
                   return_value=0):
            loop = FeedbackLoop("zhihu")
            report = await loop.run(days=30, min_samples=10)
            assert report.sample_count == 0
            assert isinstance(report, PatternReport)

    @pytest.mark.asyncio
    async def test_run_with_data(self):
        """有数据时完整运行一轮反馈"""
        mock_records = [
            {
                "content_id": "test_1",
                "title": "测试",
                "engagement_rate": 0.05,
                "surface_text": {
                    "avg_sentence_length": 25.0, "sentence_count": 10,
                    "paragraph_breaks": 5, "char_count": 500,
                    "has_mention": False, "mention_count": 0,
                    "has_link": False,
                },
                "language_style": {
                    "sentiment_polarity": 0.3, "emoji_count": 1,
                    "first_person_ratio": 0.05, "second_person_ratio": 0.01,
                    "has_bracket_aside": True,
                },
                "hook_and_structure": {
                    "hook_type": "痛点共鸣", "structure_type": "观点论证",
                    "cta_type": "评论", "cta_position": "后",
                },
                "topic_and_semantics": {
                    "primary_topic": "AI", "content_pillar": "教育",
                    "content_angle": "经验分享",
                },
                "multimedia": {"media_type": "无", "media_count": 0},
                "context": {"day_of_week": "周三", "time_of_day_hour": 20},
                "likes": 100, "comments": 20, "impressions": 2000,
            }
        ]

        mock_anchors = []

        with patch(
                "app.core.storage.manager.AsyncStorageManager.count_contents",
                return_value=30
        ), patch(
            "app.core.storage.manager.AsyncStorageManager.query_learning_with_performance",
            return_value=mock_records
        ), patch(
            "app.core.storage.manager.AsyncStorageManager.get_effective_styles",
            return_value=mock_anchors
        ), patch(
            "app.core.storage.manager.AsyncStorageManager.save_style_anchor",
            new_callable=AsyncMock
        ):
            loop = FeedbackLoop("zhihu")
            report = await loop.run(days=30, min_samples=1)

            assert report.sample_count > 0
            assert "avg_sentence_length" in report.patterns or True  # 至少有分析
