# app/core/learning_system/strategy_optimization.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List
import numpy as np
from enum import Enum


class StrategyType(Enum):
    CONTENT_CREATION = "content_creation"
    PUBLISH_TIMING = "publish_timing"
    HASHTAG_USAGE = "hashtag_usage"
    PLATFORM_SELECTION = "platform_selection"


class StrategyOptimizer(ABC):
    """策略优化器抽象基类"""

    @abstractmethod
    def optimize_strategy(self, historical_data: List[Dict[str, Any]],
                          current_performance: Dict[str, Any]) -> Dict[str, Any]:
        """优化策略"""
        pass

    @abstractmethod
    def adapt_to_changes(self, recent_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """适应环境变化"""
        pass


class ReinforcementLearningOptimizer(StrategyOptimizer):
    """强化学习优化器"""

    def __init__(self):
        self.q_table = {}
        self.learning_rate = 0.1
        self.discount_factor = 0.9
        self.exploration_rate = 0.2
        self.action_space = self._define_action_space()
        self.state_encoder = StateEncoder()

    def optimize_strategy(self, historical_data: List[Dict[str, Any]],
                          current_performance: Dict[str, Any]) -> Dict[str, Any]:
        """使用强化学习优化策略"""
        # 构建状态
        state = self.state_encoder.encode(historical_data, current_performance)

        # 选择最优动作
        best_action = self._select_best_action(state)

        # 更新Q表
        if len(historical_data) > 1:
            prev_state = self.state_encoder.encode(
                historical_data[:-1],
                historical_data[-2].get('performance', {})
            )
            reward = self._calculate_reward(current_performance)
            self._update_q_table(prev_state, best_action, reward, state)

        return {
            'recommended_action': best_action,
            'confidence': self._calculate_action_confidence(state, best_action),
            'exploration_opportunity': self._should_explore(state)
        }

    def adapt_to_changes(self, recent_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """适应环境变化"""
        # 检测概念漂移
        if self._detect_concept_drift(recent_data):
            # 降低探索率，增加学习率
            self.exploration_rate = min(self.exploration_rate * 1.1, 0.5)
            self.learning_rate = min(self.learning_rate * 1.1, 0.3)

        return self.optimize_strategy(recent_data, recent_data[-1] if recent_data else {})


class RuleBasedOptimizer(StrategyOptimizer):
    """基于规则的优化器"""

    def __init__(self):
        self.rule_engine = RuleEngine()
        self.knowledge_base = KnowledgeBase()

    def optimize_strategy(self, historical_data: List[Dict[str, Any]],
                          current_performance: Dict[str, Any]) -> Dict[str, Any]:
        """基于规则优化策略"""
        # 执行规则推理
        active_rules = self.rule_engine.match_rules(historical_data)

        recommendations = {}
        for rule in active_rules:
            if rule.condition.evaluate(historical_data):
                recommendation = rule.action.execute(historical_data)
                recommendations[rule.id] = recommendation

        return {
            'rule_based_recommendations': recommendations,
            'confidence_scores': self._calculate_rule_confidences(active_rules),
            'priority_rankings': self._rank_recommendations(recommendations)
        }

    def adapt_to_changes(self, recent_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """适应环境变化 - 规则自适应"""
        # 更新规则权重
        self.rule_engine.update_weights(recent_data)

        # 添加新规则（如果适用）
        new_rules = self._discover_new_rules(recent_data)
        for rule in new_rules:
            self.rule_engine.add_rule(rule)

        return self.optimize_strategy(recent_data, recent_data[-1] if recent_data else {})


class StateEncoder:
    """状态编码器"""

    def encode(self, historical_data: List[Dict[str, Any]],
               current_performance: Dict[str, Any]) -> str:
        """将环境状态编码为字符串"""
        # 提取关键特征
        features = {
            'avg_performance': np.mean([item.get('score', 0) for item in historical_data]),
            'trend_direction': self._calculate_trend(historical_data),
            'volatility': np.std([item.get('score', 0) for item in historical_data]),
            'platform_performance': self._extract_platform_performance(historical_data),
            'time_since_last_improvement': self._calculate_time_since_improvement(historical_data)
        }

        # 编码为字符串（简化表示）
        return str(sorted(features.items()))


class RuleEngine:
    """规则引擎"""

    def __init__(self):
        self.rules = []

    def add_rule(self, rule):
        """添加规则"""
        self.rules.append(rule)

    def match_rules(self, data: List[Dict[str, Any]]) -> List:
        """匹配适用规则"""
        return [rule for rule in self.rules if rule.applies_to(data)]


class KnowledgeBase:
    """知识库"""

    def __init__(self):
        self.facts = {}
        self.relationships = {}

    def store_fact(self, fact_id: str, fact_data: Dict[str, Any]):
        """存储事实"""
        self.facts[fact_id] = fact_data

    def get_related_facts(self, concept: str) -> List[Dict[str, Any]]:
        """获取相关事实"""
        return [fact for fact in self.facts.values() if concept in str(fact)]