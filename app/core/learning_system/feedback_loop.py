"""
自学习反馈闭环（Self-Learning Feedback Loop）

核心职责：将内容表现数据反哺到生成策略，形成"发布 → 分析 → 优化 → 发布"的正循环

架构设计：
┌─────────────────────────────────────────────────────────────┐
│                      FeedbackLoop                            │
│                                                              │
│  PatternMiner ──→ StyleAnchorUpdater ──→ ContentStrategyOptimizer
│  (发现规律)         (存储经验)             (反哺生成)         │
│                                                              │
│  数据源: LearningRecord          输出: StyleAnchorRecord      │
│         PerformanceRecord             动态权重配置            │
│                                       风格建议文本            │
└─────────────────────────────────────────────────────────────┘

Phase 策略：
  - Phase 1（数据 < 200 条）：统计方法（均值/分位/相关性）
  - Phase 2（数据 ≥ 200 条）：线性回归
  - Phase 3（数据 ≥ 1000 条）：随机森林
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta

from app.tools.logging_config import LoggingConfig
from app.core.config_manager import config
from app.core.storage import storage
from app.core.storage.models import StyleAnchorRecord


# ============================================================
#  数据类
# ============================================================

@dataclass
class FeatureAnalysis:
    """单个特征的分析结果"""
    feature_name: str  # 特征名，如 "avg_sentence_length"
    sweet_spot: Any  # 最优区间/值
    sweet_spot_desc: str  # 人类可读描述
    correlation: float  # 与互动率的相关系数 (-1 ~ 1)
    sample_count: int  # 该特征的采样数
    unit: str = ""  # 单位，如 "chars"


@dataclass
class PatternReport:
    """模式挖掘报告"""
    platform: str
    sample_count: int  # 总样本数
    generated_at: str  # 生成时间
    patterns: Dict[str, FeatureAnalysis] = field(default_factory=dict)
    avg_engagement: float = 0.0  # 平均互动率
    top_quartile_engagement: float = 0.0  # Top 25% 的平均互动率
    weight_adjustments: Dict[str, float] = field(default_factory=dict)

    def has_strong_pattern(self, feature: str, min_corr: float = 0.2) -> bool:
        """特征是否具有强相关性"""
        fa = self.patterns.get(feature)
        return fa is not None and abs(fa.correlation) >= min_corr

    def has_weak_pattern(self, feature: str, max_corr: float = 0.1) -> bool:
        """特征是否具有弱相关性"""
        fa = self.patterns.get(feature)
        return fa is not None and abs(fa.correlation) <= max_corr

    def to_style_guidance(self) -> str:
        """转换为人类可读的风格建议文本"""
        if not self.patterns:
            return ""
        lines = ["📊 【学习反馈】基于历史表现数据的风格建议："]
        for name, fa in self.patterns.items():
            if abs(fa.correlation) >= 0.15:
                arrow = "↑" if fa.correlation > 0 else "↓"
                lines.append(
                    f"  {arrow} {name}: {fa.sweet_spot_desc} "
                    f"(相关度 {fa.correlation:.2f}, {fa.sample_count} 样本)"
                )
        return "\n".join(lines)


# ============================================================
#  基类 Miner
# ============================================================
class PatternMiner:
    """模式挖掘器基类 — 采用策略模式，便于后续无缝切换 ML"""

    def __init__(self, platform: str):
        self.platform = platform
        self.log = LoggingConfig(
            log_file_path=config.logfile_path,
            log_level=config.log_level
        ).get_logger(f"PatternMiner.{platform}")

    async def mine(self, days: int = 30, min_samples: int = 10) -> PatternReport:
        """挖掘模式 — 子类应覆盖此方法"""
        raise NotImplementedError


class StatisticalMiner(PatternMiner):
    """
    Phase 1：统计方法模式挖掘器

    方法：
    1. 读取 learning_records + performance_metrics 的关联数据
    2. 对每个数值特征进行分桶统计，找出互动率最高的区间
    3. 对每个类别特征统计频率分布
    4. 计算特征与互动率的 Pearson 相关系数
    """

    async def mine(self, days: int = 30, min_samples: int = 10) -> PatternReport:
        records = await storage.query_learning_with_performance(
            platform=self.platform,
            days=days,
            min_samples=min_samples
        )

        report = PatternReport(
            platform=self.platform,
            sample_count=len(records),
            generated_at=datetime.now().isoformat(),
        )

        if not records:
            self.log.info(f"数据不足 {min_samples} 条，跳过挖掘")
            return report

        # 计算整体指标
        engagement_rates = [r.get("engagement_rate", 0) or 0 for r in records]
        report.avg_engagement = (
            sum(engagement_rates) / len(engagement_rates)
            if engagement_rates else 0
        )

        # Top 25% 互动率
        sorted_rates = sorted(engagement_rates, reverse=True)
        top_k = max(1, len(sorted_rates) // 4)
        report.top_quartile_engagement = (
            sum(sorted_rates[:top_k]) / top_k if top_k else 0
        )

        # ── 分析各个特征 ──
        # 数值特征
        numeric_features = [
            ("avg_sentence_length", "平均句长", "chars", self._bucket_sentence_length),
            ("sentiment_polarity", "情感极性", "", self._bucket_sentiment),
            ("emoji_count", "表情符号数", "", self._bucket_emoji),
            ("first_person_ratio", "第一人称占比", "", self._bucket_ratio),
            ("sentence_count", "总句数", "", self._bucket_sentence_count),
            ("paragraph_breaks", "段落数", "", self._bucket_paragraphs),
            ("mention_count", "提及数", "", self._bucket_mentions),
        ]
        # 类别特征
        categorical_features = [
            "hook_type", "structure_type", "content_pillar",
            "content_angle", "cta_type",
        ]

        # 数值特征分析
        # 数值特征分析
        for feat_key, feat_name, unit, bucket_fn in numeric_features:
            values_with_engagement = self._extract_numeric_values(records, feat_key)
            if len(values_with_engagement) < min_samples:
                continue

            analysis = self._analyze_numeric_feature(
                feat_key, feat_name, values_with_engagement, bucket_fn, unit
            )
            if analysis and analysis.sample_count >= min_samples:
                report.patterns[feat_key] = analysis

        # 类别特征分析
        for feat_key in categorical_features:
            values_with_engagement = self._extract_categorical_values(records, feat_key)
            if len(values_with_engagement) < min_samples:
                continue
            analysis = self._analyze_categorical_feature(
                feat_key, values_with_engagement
            )
            if analysis and analysis.sample_count >= min_samples:
                report.patterns[feat_key] = analysis

            # 计算权重调整建议
        report.weight_adjustments = self._calculate_weight_adjustments(report)

        self.log.info(
            f"模式挖掘完成: {len(report.patterns)} 个特征, "
            f"样本量 {report.sample_count}"
        )
        return report

    # ── 数据提取 ──

    @staticmethod
    def _extract_numeric_values(
            records: List[dict], field: str
    ) -> List[Tuple[float, float]]:
        """提取数值特征值 + 互动率 对"""
        result = []
        for r in records:
            # 优先从 surface_text 取，找不到再从 language_style 取（避免同名字段重复提取）
            surface = r.get("surface_text") or {}
            val = surface.get(field)
            if val is not None and isinstance(val, (int, float)):
                result.append((float(val), r.get("engagement_rate", 0) or 0))
                continue

            lang = r.get("language_style") or {}
            val = lang.get(field)
            if val is not None and isinstance(val, (int, float)):
                result.append((float(val), r.get("engagement_rate", 0) or 0))

        return result

    @staticmethod
    def _extract_categorical_values(
            records: List[dict], field: str
    ) -> List[Tuple[str, float]]:
        """提取类别特征值 + 互动率 对"""
        result = []
        for r in records:
            for src_key in ("hook_and_structure", "topic_and_semantics"):
                src = r.get(src_key) or {}
                val = src.get(field)
                if val and isinstance(val, str):
                    result.append((val, r.get("engagement_rate", 0) or 0))
                    break
        return result

    # ── 数值分桶 ──

    @staticmethod
    def _bucket_sentence_length(val: float) -> str:
        if val <= 15:
            return "≤15 chars"
        elif val <= 25:
            return "16-25 chars"
        elif val <= 35:
            return "26-35 chars"
        elif val <= 50:
            return "36-50 chars"
        else:
            return ">50 chars"

    @staticmethod
    def _bucket_sentiment(val: float) -> str:
        if val <= -0.3:
            return "消极"
        elif val <= -0.1:
            return "偏消极"
        elif val <= 0.1:
            return "中性"
        elif val <= 0.3:
            return "偏积极"
        else:
            return "积极"

    @staticmethod
    def _bucket_emoji(val: float) -> str:
        val_int = int(val)
        if val_int == 0:
            return "0 个"
        elif val_int <= 2:
            return "1-2 个"
        elif val_int <= 5:
            return "3-5 个"
        else:
            return ">5 个"

    @staticmethod
    def _bucket_ratio(val: float) -> str:
        if val <= 0.01:
            return "低 (<1%)"
        elif val <= 0.05:
            return "中 (1-5%)"
        elif val <= 0.15:
            return "高 (5-15%)"
        else:
            return "很高 (>15%)"

    @staticmethod
    def _bucket_sentence_count(val: float) -> str:
        val_int = int(val)
        if val_int <= 5:
            return "≤5 句"
        elif val_int <= 10:
            return "6-10 句"
        elif val_int <= 20:
            return "11-20 句"
        else:
            return ">20 句"

    @staticmethod
    def _bucket_paragraphs(val: float) -> str:
        val_int = int(val)
        if val_int <= 3:
            return "≤3 段"
        elif val_int <= 6:
            return "4-6 段"
        elif val_int <= 10:
            return "7-10 段"
        else:
            return ">10 段"

    @staticmethod
    def _bucket_mentions(val: float) -> str:
        val_int = int(val)
        if val_int == 0:
            return "0 个"
        elif val_int <= 2:
            return "1-2 个"
        else:
            return ">2 个"

    # ── 分析逻辑 ──

    def _analyze_numeric_feature(
            self,
            feat_key: str,
            feat_name: str,
            values: List[Tuple[float, float]],
            bucket_fn,
            unit: str,
    ) -> Optional[FeatureAnalysis]:
        """分析数值特征：分桶 → 计算每个桶的平均互动率 → 找出最优区间"""
        if len(values) < 3:
            return None

        # 分桶
        buckets: Dict[str, List[float]] = {}
        for val, engagement in values:
            label = bucket_fn(val)
            if label not in buckets:
                buckets[label] = []
            buckets[label].append(engagement)

        # 计算每个桶的平均互动率
        bucket_avgs: List[Tuple[str, float, int]] = []
        for label, engagements in buckets.items():
            avg = sum(engagements) / len(engagements)
            bucket_avgs.append((label, avg, len(engagements)))

        if not bucket_avgs:
            return None

        # 找最优桶
        best_label, best_avg, best_count = max(bucket_avgs, key=lambda x: x[1])

        # 计算 Pearson 相关系数（简化版）
        values_only = [v[0] for v in values]
        engagements_only = [v[1] for v in values]
        corr = self._pearson(values_only, engagements_only)

        return FeatureAnalysis(
            feature_name=feat_name,
            sweet_spot=best_label,
            sweet_spot_desc=f"最优区间: {best_label} (平均互动率 {best_avg:.4f})",
            correlation=round(corr, 4),
            sample_count=len(values),
            unit=unit,
        )

    def _analyze_categorical_feature(
            self,
            feat_key: str,
            values: List[Tuple[str, float]],
    ) -> Optional[FeatureAnalysis]:
        """分析类别特征：统计频率 + 平均互动率"""
        if len(values) < 3:
            return None

        # 统计
        categories: Dict[str, List[float]] = {}
        for val, engagement in values:
            if val not in categories:
                categories[val] = []
            categories[val].append(engagement)

        # 找出现频率最高的类别 + 互动率最高的类别
        cat_avgs: List[Tuple[str, float, float]] = []
        for cat, engagements in categories.items():
            avg = sum(engagements) / len(engagements)
            freq = len(engagements) / len(values)
            cat_avgs.append((cat, avg, freq))

        if not cat_avgs:
            return None

        # 按频率排序
        most_frequent = max(cat_avgs, key=lambda x: x[2])
        # 按互动率排序
        best_performing = max(cat_avgs, key=lambda x: x[1])

        return FeatureAnalysis(
            feature_name=feat_key,
            sweet_spot=best_performing[0],
            sweet_spot_desc=(
                f"最优: {best_performing[0]} (互动率 {best_performing[1]:.4f}), "
                f"最常用: {most_frequent[0]} (频率 {most_frequent[2]:.1%})"
            ),
            correlation=round(best_performing[1], 4),
            sample_count=len(values),
        )

    @staticmethod
    def _pearson(x: List[float], y: List[float]) -> float:
        """Pearson 相关系数"""
        n = len(x)
        if n < 3:
            return 0.0
        try:
            sum_x = sum(x)
            sum_y = sum(y)
            sum_xy = sum(a * b for a, b in zip(x, y))
            sum_x2 = sum(a * a for a in x)
            sum_y2 = sum(b * b for b in y)
            numerator = n * sum_xy - sum_x * sum_y
            denominator = math.sqrt((n * sum_x2 - sum_x ** 2) * (n * sum_y2 - sum_y ** 2))
            if denominator == 0:
                return 0.0
            return numerator / denominator
        except (ZeroDivisionError, ValueError, OverflowError):
            return 0.0

    @staticmethod
    def _calculate_weight_adjustments(report: PatternReport) -> Dict[str, float]:
        """
        根据模式报告计算 QualityGate 权重微调

        规则：
        - 如果某个特征的 correlation > 0.2，对应维度的权重 +0.03
        - 如果某个特征的 correlation < 0.1，对应维度的权重 -0.02
        - 总权重和保持为 1.0
        """
        # 特征 → 评分维度的映射
        feature_dim_map = {
            "avg_sentence_length": "structure_readability",
            "sentence_count": "structure_readability",
            "paragraph_breaks": "structure_readability",
            "sentiment_polarity": "handwriting_score",
            "first_person_ratio": "handwriting_score",
            "emoji_count": "handwriting_score",
            "hook_type": "handwriting_score",
            "structure_type": "structure_readability",
            "content_pillar": "information_density",
            "content_angle": "viewpoint_uniqueness",
        }

        adjustments: Dict[str, float] = {}
        for feat_name, analysis in report.patterns.items():
            dim = feature_dim_map.get(feat_name)
            if dim is None:
                continue
            corr = abs(analysis.correlation)
            if corr >= 0.2:
                adjustments[dim] = adjustments.get(dim, 0) + 0.03
            elif corr <= 0.1:
                adjustments[dim] = adjustments.get(dim, 0) - 0.02

        return adjustments


# ============================================================
#  StyleAnchorUpdater — 风格锚点更新器
# ============================================================

class StyleAnchorUpdater:
    """
    风格锚点更新器

    职责：
    1. 将 PatternReport 中有价值的模式写入 style_anchors 表
    2. 更新已有锚点的 effectiveness_score
    3. 清理过期的低效锚点
    """

    def __init__(self, platform: str):
        self.platform = platform
        self.log = LoggingConfig(
            log_file_path=config.logfile_path,
            log_level=config.log_level
        ).get_logger(f"StyleAnchorUpdater.{platform}")

    async def update_from_report(self, report: PatternReport) -> int:
        """从模式报告更新风格锚点，返回更新的数量"""
        if not report.patterns:
            return 0

        updated = 0
        for feat_name, analysis in report.patterns.items():
            # 只保留有意义的模式（相关性 >= 0.15）
            if abs(analysis.correlation) < 0.15:
                continue

            anchor = StyleAnchorRecord(
                platform=self.platform,
                name=f"auto_{feat_name}",
                content=json.dumps({
                    "sweet_spot": analysis.sweet_spot,
                    "sweet_spot_desc": analysis.sweet_spot_desc,
                    "correlation": analysis.correlation,
                    "unit": analysis.unit,
                }, ensure_ascii=False),
                tags=json.dumps([feat_name, "auto_extracted", self.platform], ensure_ascii=False),
                effectiveness_score=abs(analysis.correlation),
                source="learning",
            )
            await storage.save_style_anchor(anchor)
            updated += 1

        self.log.info(f"更新了 {updated} 个风格锚点")
        return updated

    async def cleanup_stale(self, min_score: float = 0.05, max_age_days: int = 60) -> int:
        """清理低效的自动锚点"""
        # 仅做记录，真正的清理由管理员手动执行
        anchors = await storage.get_effective_styles(
            platform=self.platform, min_score=min_score
        )
        stale_count = sum(1 for a in anchors if a.effectiveness_score < min_score)
        if stale_count:
            self.log.info(f"发现 {stale_count} 个低效锚点 (分数 < {min_score})")
        return stale_count


# ============================================================
#  ContentStrategyOptimizer — 内容策略优化器
# ============================================================

class ContentStrategyOptimizer:
    """
    内容策略优化器

    职责：
    1. 为 QualityGate 提供动态权重配置
    2. 为 ContentPipeline._anchor_style 提供数据驱动的风格建议
    3. 校准 QualityGate 评分
    """

    def __init__(self, platform: str):
        self.platform = platform
        self.log = LoggingConfig(
            log_file_path=config.logfile_path,
            log_level=config.log_level
        ).get_logger(f"ContentStrategyOptimizer.{platform}")

    async def get_dynamic_weights(self) -> Dict[str, float]:
        """获取动态评分权重"""
        base = {
            "handwriting_score": 0.30,
            "information_density": 0.25,
            "viewpoint_uniqueness": 0.20,
            "structure_readability": 0.15,
            "platform_adaptation": 0.10,
        }

        # 读取最近一次 PatternReport 的权重调整
        anchors = await storage.get_effective_styles(
            platform=self.platform, min_score=0.0, limit=50
        )
        adjustments: Dict[str, float] = {}
        for anchor in anchors:
            if anchor.source != "learning" or not anchor.content:
                continue
            try:
                content = json.loads(anchor.content)
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(content, dict) and "correlation" in content:
                corr = abs(content["correlation"])
                # 根据特征名推断影响的维度
                name = anchor.name.replace("auto_", "")
                if name in ("avg_sentence_length", "sentence_count", "paragraph_breaks"):
                    dim = "structure_readability"
                elif name in ("sentiment_polarity", "first_person_ratio", "emoji_count", "hook_type"):
                    dim = "handwriting_score"
                elif name in ("content_pillar",):
                    dim = "information_density"
                elif name in ("content_angle",):
                    dim = "viewpoint_uniqueness"
                else:
                    continue

                if corr >= 0.2:
                    adjustments[dim] = adjustments.get(dim, 0) + 0.03
                elif corr <= 0.1:
                    adjustments[dim] = adjustments.get(dim, 0) - 0.02

        # 应用调整（确保不超过合理范围）
        for dim, adj in adjustments.items():
            if dim in base:
                base[dim] = max(0.05, min(0.50, base[dim] + adj))

        # 归一化到 1.0
        total = sum(base.values())
        if total > 0:
            for dim in base:
                base[dim] = round(base[dim] / total, 4)

        return base

    async def get_style_guidance(self, hot_title: str = "") -> str:
        """生成数据驱动的风格建议文本，供 _anchor_style 注入"""
        anchors = await storage.get_effective_styles(
            platform=self.platform, min_score=0.2, limit=5
        )
        if not anchors:
            return ""

        lines = ["📊 【历史数据提示】以下特征在同类内容中表现较好："]
        for a in anchors:
            try:
                content = json.loads(a.content) if isinstance(a.content, str) else {}
            except (json.JSONDecodeError, TypeError):
                content = {}
            desc = content.get("sweet_spot_desc", a.content[:80] if a.content else "")
            score = a.effectiveness_score
            lines.append(f"  • {a.name.replace('auto_', '')}: {desc} (有效度: {score:.2f})")

        return "\n".join(lines)

    async def get_quality_gate_report(self) -> Optional[PatternReport]:
        """生成最近的完整分析报告"""
        miner = StatisticalMiner(self.platform)
        return await miner.mine(days=30, min_samples=5)


# ============================================================
#  FeedbackLoop — 反馈闭环编排器（对外统一入口）
# ============================================================

class FeedbackLoop:
    """
    自学习反馈闭环 — 对外统一接口

    使用示例：
        loop = FeedbackLoop("zhihu")
        await loop.run()                          # 执行完整一轮反馈
        await loop.record("content_id_xxx")       # 单条内容记录

    自动选择矿工策略：
        < 200 条  → StatisticalMiner（统计方法）
        ≥ 200 条  → RegressionMiner（线性回归）[预留]
        ≥ 1000 条 → RandomForestMiner（随机森林）[预留]
    """

    def __init__(self, platform: str, storage_manager=None):
        self.platform = platform
        self.storage = storage_manager or storage
        self.log = LoggingConfig(
            log_file_path=config.logfile_path,
            log_level=config.log_level
        ).get_logger(f"FeedbackLoop.{platform}")

        # 子组件
        self.miner: PatternMiner = StatisticalMiner(platform)
        self.anchor_updater = StyleAnchorUpdater(platform)
        self.strategy_optimizer = ContentStrategyOptimizer(platform)

    async def run(self, days: int = 30, min_samples: int = 10) -> PatternReport:
        """
        执行一轮完整的反馈闭环

        流程：
        1. 挖掘模式（PatternMiner）
        2. 更新风格锚点（StyleAnchorUpdater）
        3. 输出策略优化（ContentStrategyOptimizer — 由 QualityGate/Pipeline 消费）

        Args:
            days: 回溯天数
            min_samples: 最小样本数

        Returns:
            模式挖掘报告
        """
        self.log.info(f"🔄 开始反馈闭环: platform={self.platform}, days={days}")

        # 1. 自动选择矿工
        count = await self.storage.count_contents(platform=self.platform)
        self._select_miner(count)
        self.log.info(f"  样本量: {count}, 使用矿工: {type(self.miner).__name__}")

        if count == 0:
            self.log.info("无数据，跳过挖掘")
            return PatternReport(
                platform=self.platform,
                sample_count=0,
                generated_at=datetime.now().isoformat(),
            )

        # 2. 挖掘模式
        report = await self.miner.mine(days=days, min_samples=min_samples)

        # 3. 更新风格锚点
        if report.patterns:
            updated = await self.anchor_updater.update_from_report(report)
            self.log.info(f"  更新了 {updated} 个风格锚点")

            # 4. 计算权重调整
            weights = await self.strategy_optimizer.get_dynamic_weights()
            self.log.info(f"  动态权重: {weights}")

            # 5. 清理低效锚点
            stale = await self.anchor_updater.cleanup_stale()
            if stale:
                self.log.info(f"  发现 {stale} 个低效锚点")

        self.log.info(f"✅ 反馈闭环完成")
        return report

    async def record(self, content_id: str, platform: Optional[str] = None) -> None:
        """
        记录一条新内容的表现数据（实时触发）

        当 ContentPipeline 生成完成 + 平台数据采集到后调用此方法，
        增量更新模式分析。

        Args:
            content_id: 内容 ID
            platform: 平台名（默认使用 self.platform）
        """
        plat = platform or self.platform
        self.log.debug(f"记录内容表现: {content_id[:8]}... ({plat})")

        # 这里只做预留，实际增量更新在数据量足够时再开启
        # 当前版本依赖定时的 run() 做全量分析

    def _select_miner(self, total_count: int):
        """根据数据量选择矿工策略（预留 ML 升级路径）"""
        if total_count >= 1000:
            # TODO: 切换为 RandomForestMiner
            self.miner = StatisticalMiner(self.platform)
        elif total_count >= 200:
            # TODO: 切换为 RegressionMiner
            self.miner = StatisticalMiner(self.platform)
        else:
            self.miner = StatisticalMiner(self.platform)
