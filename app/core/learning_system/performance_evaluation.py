# app/core/learning_system/performance_evaluation.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from dataclasses import dataclass
import numpy as np


@dataclass
class PerformanceScore:
    """性能评分数据结构"""
    composite_score: float
    engagement_score: float
    content_quality_score: float
    timing_score: float
    breakdown: Dict[str, float]
    confidence: float


class PerformanceEvaluator(ABC):
    """性能评估器抽象基类"""

    @abstractmethod
    def evaluate(self, metrics: Dict[str, Any]) -> PerformanceScore:
        """评估性能"""
        pass

    @abstractmethod
    def get_baseline_comparison(self, score: PerformanceScore) -> Dict[str, Any]:
        """与基线比较"""
        pass


class CompositePerformanceEvaluator(PerformanceEvaluator):
    """综合性能评估器"""

    def __init__(self):
        self.weights = self._initialize_weights()
        self.baseline_calculator = BaselineCalculator()

    def evaluate(self, metrics: Dict[str, Any]) -> PerformanceScore:
        """综合评估性能"""
        # 计算各维度得分
        engagement_score = self._calculate_engagement_score(metrics)
        content_score = self._calculate_content_score(metrics)
        timing_score = self._calculate_timing_score(metrics)

        # 计算综合得分
        composite_score = (
                engagement_score * self.weights['engagement'] +
                content_score * self.weights['content'] +
                timing_score * self.weights['timing']
        )

        # 计算置信度
        confidence = self._calculate_confidence(metrics)

        return PerformanceScore(
            composite_score=composite_score,
            engagement_score=engagement_score,
            content_quality_score=content_score,
            timing_score=timing_score,
            breakdown={
                "engagement": engagement_score,
                "content": content_score,
                "timing": timing_score
            },
            confidence=confidence
        )

    def _calculate_engagement_score(self, metrics: Dict[str, Any]) -> float:
        """计算互动得分"""
        engagement = metrics.get('engagement_metrics', {})

        # 标准化各项指标
        likes_norm = self._normalize_metric(engagement.get('likes', 0), 'likes')
        comments_norm = self._normalize_metric(engagement.get('comments', 0), 'comments')
        shares_norm = self._normalize_metric(engagement.get('shares', 0), 'shares')
        ctr_norm = self._normalize_metric(engagement.get('click_through_rate', 0), 'ctr')

        # 加权平均
        score = (
                likes_norm * 0.3 +
                comments_norm * 0.3 +
                shares_norm * 0.25 +
                ctr_norm * 0.15
        )

        return min(score, 1.0)  # 限制在0-1范围内

    def _calculate_content_score(self, metrics: Dict[str, Any]) -> float:
        """计算内容质量得分"""
        features = metrics.get('content_features', {})

        # 内容质量因子
        readability = self._calculate_readability_score(features)
        creativity = self._calculate_creativity_score(features)
        relevance = self._calculate_relevance_score(features)

        return (readability + creativity + relevance) / 3

    def _calculate_timing_score(self, metrics: Dict[str, Any]) -> float:
        """计算时间策略得分"""
        timing = metrics.get('timing_factors', {})
        publish_hour = timing.get('publish_hour', 12)

        # 最佳发布时段分析
        optimal_hours = [9, 12, 18, 21]  # 根据数据调整
        is_optimal = publish_hour in optimal_hours

        # 发布频率分析
        interval = timing.get('post_interval_hours', 24)
        frequency_score = self._evaluate_frequency(interval)

        return 0.6 if is_optimal else 0.4 + frequency_score * 0.4

    def _normalize_metric(self, value: float, metric_type: str) -> float:
        """标准化指标值"""
        # 基于历史数据的百分位数标准化
        baseline = self.baseline_calculator.get_baseline(metric_type)
        return min(value / baseline['median'], 2.0) / 2.0  # 归一化到0-1

    def _initialize_weights(self) -> Dict[str, float]:
        """初始化权重"""
        return {
            'engagement': 0.5,
            'content': 0.3,
            'timing': 0.2
        }


class BaselineCalculator:
    """基线计算器"""

    def __init__(self):
        self.historical_data = []

    def get_baseline(self, metric_type: str) -> Dict[str, float]:
        """获取指标基线数据"""
        # 返回历史数据的统计信息
        values = [item[metric_type] for item in self.historical_data if metric_type in item]
        if not values:
            return {'mean': 0, 'median': 0, 'std': 1}

        return {
            'mean': np.mean(values),
            'median': np.median(values),
            'std': np.std(values)
        }
