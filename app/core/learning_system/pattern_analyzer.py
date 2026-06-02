# app/core/learning_system/pattern_analysis.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Tuple
from collections import defaultdict
import statistics


class PatternAnalyzer(ABC):
    """模式分析器抽象基类"""

    @abstractmethod
    def analyze_success_patterns(self, high_performers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析成功模式"""
        pass

    @abstractmethod
    def analyze_failure_patterns(self, low_performers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析失败模式"""
        pass

    @abstractmethod
    def generate_recommendations(self, patterns: Dict[str, Any]) -> List[str]:
        """生成改进建议"""
        pass


class AdvancedPatternAnalyzer(PatternAnalyzer):
    """高级模式分析器"""

    def __init__(self):
        self.pattern_detectors = {
            'title_patterns': TitlePatternDetector(),
            'content_structures': ContentStructureDetector(),
            'timing_optimizations': TimingPatternDetector(),
            'hashtag_strategies': HashtagPatternDetector()
        }

    def analyze_success_patterns(self, high_performers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析成功模式"""
        patterns = {}

        for pattern_type, detector in self.pattern_detectors.items():
            patterns[pattern_type] = detector.detect_success_patterns(high_performers)

        return {
            'success_patterns': patterns,
            'statistical_significance': self._calculate_statistical_significance(high_performers),
            'confidence_intervals': self._calculate_confidence_intervals(high_performers)
        }

    def analyze_failure_patterns(self, low_performers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析失败模式"""
        patterns = {}

        for pattern_type, detector in self.pattern_detectors.items():
            patterns[pattern_type] = detector.detect_failure_patterns(low_performers)

        return {
            'failure_patterns': patterns,
            'risk_indicators': self._identify_risk_indicators(low_performers),
            'correlation_matrix': self._calculate_correlations(low_performers)
        }

    def generate_recommendations(self, patterns: Dict[str, Any]) -> List[str]:
        """生成改进建议"""
        recommendations = []

        success_patterns = patterns.get('success_patterns', {})
        failure_patterns = patterns.get('failure_patterns', {})

        # 基于成功模式的建议
        for pattern_type, pattern_data in success_patterns.items():
            if pattern_data:
                recommendations.extend(self._generate_positive_recommendations(pattern_type, pattern_data))

        # 基于失败模式的建议
        for pattern_type, pattern_data in failure_patterns.items():
            if pattern_data:
                recommendations.extend(self._generate_negative_recommendations(pattern_type, pattern_data))

        return recommendations

    def _calculate_statistical_significance(self, data: List[Dict[str, Any]]) -> Dict[str, float]:
        """计算统计显著性"""
        # 使用t检验或其他统计方法
        pass

    def _calculate_confidence_intervals(self, data: List[Dict[str, Any]]) -> Dict[str, tuple]:
        """计算置信区间"""
        pass

    def _identify_risk_indicators(self, low_performers: List[Dict[str, Any]]) -> List[str]:
        """识别风险指标"""
        indicators = []

        # 分析低表现内容的共同特征
        common_features = self._find_common_features(low_performers)

        for feature, value in common_features.items():
            if self._is_risk_indicator(feature, value):
                indicators.append(f"Avoid {feature}: {value}")

        return indicators


class TitlePatternDetector:
    """标题模式检测器"""

    def detect_success_patterns(self, high_performers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """检测成功标题模式"""
        titles = [item.get('title', '') for item in high_performers if 'title' in item]

        # 分析标题特征
        patterns = {
            'length_distribution': self._analyze_length_distribution(titles),
            'word_frequency': self._analyze_word_frequency(titles),
            'sentiment_analysis': self._analyze_sentiment(titles),
            'question_mark_usage': self._analyze_question_usage(titles),
            'number_usage': self._analyze_number_usage(titles)
        }

        return patterns

    def detect_failure_patterns(self, low_performers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """检测失败标题模式"""
        titles = [item.get('title', '') for item in low_performers if 'title' in item]

        # 寻找负面模式
        patterns = {
            'overused_phrases': self._find_overused_phrases(titles),
            'clickbait_indicators': self._detect_clickbait_indicators(titles),
            'negative_sentiment_indicators': self._detect_negative_sentiment(titles)
        }

        return patterns


class ContentStructureDetector:
    """内容结构检测器"""

    def detect_success_patterns(self, high_performers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """检测成功内容结构"""
        contents = [item.get('content', '') for item in high_performers if 'content' in item]

        patterns = {
            'paragraph_distribution': self._analyze_paragraph_structure(contents),
            'sentence_length_avg': self._analyze_sentence_length(contents),
            'media_placement': self._analyze_media_placement(contents),
            'call_to_action_frequency': self._analyze_cta_frequency(contents)
        }

        return patterns

    def detect_failure_patterns(self, low_performers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """检测失败内容结构"""
        contents = [item.get('content', '') for item in low_performers if 'content' in item]

        patterns = {
            'length_issues': self._detect_length_problems(contents),
            'structure_problems': self._detect_structure_issues(contents),
            'engagement_kills': self._detect_engagement_kills(contents)
        }

        return patterns