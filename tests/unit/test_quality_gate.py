"""
测试 QualityScore 质量评分数据类

覆盖范围：
- 综合评分计算（权重验证）
- 边界值：全 0 分、满分
- to_dict 序列化
- 各维度独立影响
"""

import pytest
from app.core.content_pipeline.quality_gate import QualityScore


class TestQualityScore:
    """QualityScore 的纯逻辑测试，不需要任何 mock"""

    def test_default_score_is_zero(self):
        """默认所有维度为 0，综合得分应为 0"""
        score = QualityScore()
        assert score.overall_score == 0.0

    def test_perfect_score(self):
        """满分 10 分时，综合得分应为 10"""
        score = QualityScore(
            handwriting_score=10.0,
            information_density=10.0,
            viewpoint_uniqueness=10.0,
            structure_readability=10.0,
            platform_adaptation=10.0,
        )
        assert score.overall_score == 10.0

    def test_weight_verification(self):
        """验证权重：手写感权重 0.30，只改它应贡献 3 分"""
        score = QualityScore(handwriting_score=10.0)
        assert score.overall_score == pytest.approx(3.0)

    def test_mid_range_score(self):
        """中等分数验证"""
        score = QualityScore(
            handwriting_score=7.0,
            information_density=6.0,
            viewpoint_uniqueness=8.0,
            structure_readability=5.0,
            platform_adaptation=9.0,
        )
        expected = (7.0 * 0.30 + 6.0 * 0.25 + 8.0 * 0.20 +
                    5.0 * 0.15 + 9.0 * 0.10)
        assert score.overall_score == pytest.approx(expected)

    def test_partial_dimensions(self):
        """只有部分维度有值"""
        score = QualityScore(
            handwriting_score=8.0,
            information_density=7.0,
        )
        expected = 8.0 * 0.30 + 7.0 * 0.25
        assert score.overall_score == pytest.approx(expected)

    def test_to_dict_includes_overall(self):
        """to_dict 输出应包含 overall_score"""
        score = QualityScore(handwriting_score=8.0)
        d = score.to_dict()
        assert "overall_score" in d
        assert d["overall_score"] == 8.0 * 0.30
        assert d["handwriting_score"] == 8.0

    def test_individual_scores_are_independent(self):
        """各维度互不影响"""
        score = QualityScore(handwriting_score=9.0)
        assert score.information_density == 0.0
        assert score.viewpoint_uniqueness == 0.0

    @pytest.mark.parametrize("handwriting,expected_part", [
        (0.0, 0.0),
        (5.0, 1.5),
        (10.0, 3.0),
    ])
    def test_handwriting_contributes_correctly(self, handwriting, expected_part):
        """参数化测试：手写感维度贡献值"""
        score = QualityScore(handwriting_score=handwriting)
        assert score.overall_score == pytest.approx(expected_part)
