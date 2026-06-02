"""
内容数据采集与 Schema 编排器

职责：
1. 从各平台采集原始数据
2. 使用 NLP 分析文本特征
3. 使用 LLM 分析深层语义
4. 将所有数据映射到 schema.json 统一格式
"""
from typing import Dict, Any, Optional
from datetime import datetime
import asyncio
import json
from app.core.config_manager import config
from app.tools.logging_config import LoggingConfig


class ContentMetricsCollector:
    """内容指标收集器 — 整合平台数据 + NLP + LLM 输出完整 schema 结构"""

    def __init__(self, storage_manager=None, model=None):
        self.storage_manager = storage_manager
        self.model = model or config.learning_system['model']

        # 懒加载分析器
        self._content_analyzer = None
        self._llm_analyzer = None

        self.log = LoggingConfig(log_file_path=config.logfile_path, log_level=config.log_level).get_logger(
            f"{self.__class__.__name__}")

    # ── 属性：延迟初始化分析器 ────────────────────────────────
    @property
    def content_analyzer(self):
        if self._content_analyzer is None:
            from app.core.learning_system.content_analyzer import ContentAnalyzer
            self._content_analyzer = ContentAnalyzer()
        return self._content_analyzer

    @property
    def llm_analyzer(self):
        if self._llm_analyzer is None:
            from app.core.learning_system.llm_analyzer import LLMContentAnalyzer
            self._llm_analyzer = LLMContentAnalyzer(model=self.model)
        return self._llm_analyzer

    # ── 对外接口 ──────────────────────────────────────────────
    async def collect_content_metrics(self, content_id: str, platform: str) -> Dict[str, Any]:
        """
        收集内容表现指标 → 返回符合 schema.json 的完整结构

        步骤：
        1. 从平台 API 获取原始数据
        2. NLP 分析文本表层 + 语言风格
        3. LLM 分析底层语义 + 结构
        4. 提取表现反馈 + 上下文
        5. 映射为统一 schema 返回
        """
        # 1. 平台数据
        platform_data = await self._fetch_platform_data(content_id, platform)
        if not platform_data:
            self.log.warning(f"[{platform}] 未能获取数据: content_id={content_id}")
            return {}

        # 2. 内容特征分析（NLP + LLM 并行执行）
        content_features = await self._analyze_content_features(platform_data)

        # 3. 表现反馈
        performance_feedback = self._collect_performance_feedback(platform_data)

        # 4. 上下文环境
        context = self._collect_context(platform_data)

        # 5. 构建完整 schema
        return self._build_schema_output(
            platform_data=platform_data,
            content_features=content_features,
            performance_feedback=performance_feedback,
            context=context,
            platform=platform,
        )

    # ── 数据获取 ──────────────────────────────────────────────
    async def _fetch_platform_data(self, content_id: str, platform: str) -> Dict[str, Any]:
        """从平台 API 获取原始指标数据"""
        if platform == "zhihu":
            from app.request_spiders.zhihu_platform.zhihu_metrics_collector import (
                AsyncZhihuMetricsCollector,
            )
            collector = AsyncZhihuMetricsCollector()
            return await collector.fetch_answer_metrics(content_id)
        return {}

    # ── 内容特征分析（核心） ──────────────────────────────────
    async def _analyze_content_features(self, platform_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        综合 NLP + LLM 分析内容全部特征字段

        执行流程：
        1. NLP 分析 → surface_text + language_style + multimedia
        2. LLM 分析 → hook_and_structure + topic_and_semantics （耗时操作，独立并发）
        """
        meta = platform_data.get("content_meta", {})
        title = meta.get("title", "")
        excerpt = meta.get("excerpt", "")

        # ── 1. NLP 分析（本地，快速） ──
        surface_text = self.content_analyzer.analyze_surface_text(title, excerpt)  # 文本表层特征
        language_style = self.content_analyzer.analyze_language_style(excerpt)  # 语言风格
        multimedia = self.content_analyzer.analyze_multimedia(platform_data)  # 多媒体特征

        # ── 2. LLM 分析（远程调用，独立并发） ──
        llm_result = await self.llm_analyzer.analyze_deep_features(title, excerpt)
        hook_and_structure = llm_result.get("hook_and_structure", {})
        topic_and_semantics = llm_result.get("topic_and_semantics", {})

        # 补充：LLM 中分析的 language_style 深层字段回填
        llm_lang = llm_result.get("language_style_deep", {})
        if llm_lang.get("sentiment_variance"):
            language_style["sentiment_variance"] = llm_lang["sentiment_variance"]
        if llm_lang.get("jargon_ratio"):
            language_style["jargon_ratio"] = llm_lang["jargon_ratio"]

        return {
            "surface_text": surface_text,
            "hook_and_structure": hook_and_structure,
            "language_style": language_style,
            "topic_and_semantics": topic_and_semantics,
            "multimedia": multimedia,
        }

    # ── 表现反馈 ──────────────────────────────────────────────
    @staticmethod
    def _collect_performance_feedback(platform_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        将平台指标映射到 schema.performance_feedback

        知乎 → schema 映射：
          total.pv        → impressions
          total.upvote    → likes
          total.share     → retweets（知乎无严格转发概念，share 近似）
          total.comment   → replies
          total.collect   → bookmarks
          today.pv        → （用于计算互动速度）
          advanced.finish_read_percent → （完读率额外保留）
        """
        total = platform_data.get("total", {})
        yesterday = platform_data.get("yesterday", {})
        advanced = platform_data.get("advanced", {})

        # 基础指标
        impressions = total.get("pv", 0)
        likes = total.get("upvote", 0)
        comments = total.get("comment", 0)
        shares = total.get("share", 0)
        bookmarks = total.get("collect", 0)

        # 新增关注（知乎用 follower_translate 近似）
        new_follows = total.get("new_like", 0) or advanced.get("follower_translate", 0)

        # 互动率计算（按展示量）
        engagement_rate = 0.0
        if impressions and impressions > 0:
            total_interactions = likes + comments + shares + bookmarks
            engagement_rate = round(total_interactions / impressions, 6)

        # 回复速度（从 yesterday/today 数据推测）
        reply_velocity = {}
        yesterday_pv = yesterday.get("pv", 0)
        if yesterday_pv:
            reply_velocity["24h"] = float(yesterday.get("comment", 0))

        return {
            "impressions": impressions,
            "likes": likes,
            "retweets": shares,
            "replies": comments,
            "quote_tweets": total.get("re_pin", 0),
            "bookmarks": bookmarks,
            "link_clicks": total.get("show", 0),
            "profile_clicks": 0,
            "follows_gained": new_follows,
            "negative_feedback": 0,
            "reply_sentiment": {
                "positive": 0.0,
                "neutral": 0.0,
                "negative": 0.0,
            },
            "engagement_rate_by_impression": engagement_rate,
            "engagement_rate_by_followers": 0.0,
            "reply_velocity": reply_velocity,
            "lifetime_value_48h_ratio": 0.0,
            "quality_score": 0.0,
        }

    # ── 上下文环境 ────────────────────────────────────────────
    @staticmethod
    def _collect_context(platform_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        提取发布上下文 → schema.context

        注意：部分字段（粉丝数、24h 发帖频率）需后续从其他数据源补充，
        当前先用默认值占位。
        """
        meta = platform_data.get("content_meta", {})
        publish_time = meta.get("created_time")

        if publish_time and isinstance(publish_time, datetime):
            hour = publish_time.hour
            weekday = publish_time.weekday()
            weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            return {
                "follower_count_at_post": 0,
                "average_engagement_7d": 0.0,
                "day_of_week": weekday_names[weekday] if 0 <= weekday <= 6 else "",
                "time_of_day_hour": hour,
                "is_weekend": weekday >= 5,
                "post_frequency_before_24h": 0,
                "is_paid_promotion": False,
                "competitor_similar_post_id": None,
            }

        now = datetime.now()
        return {
            "follower_count_at_post": 0,
            "average_engagement_7d": 0.0,
            "day_of_week": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()],
            "time_of_day_hour": now.hour,
            "is_weekend": now.weekday() >= 5,
            "post_frequency_before_24h": 0,
            "is_paid_promotion": False,
            "competitor_similar_post_id": None,
        }

    # ── Schema 构建 ───────────────────────────────────────────
    @staticmethod
    def _build_schema_output(
            platform_data: Dict[str, Any],
            content_features: Dict[str, Any],
            performance_feedback: Dict[str, Any],
            context: Dict[str, Any],
            platform: str,
    ) -> Dict[str, Any]:
        """
        将所有数据组合为 schema.json 定义的完整结构

        schema.json required fields:
          post_id, author_id, platform, created_at,
          content_features, performance_feedback, context
        """
        meta = platform_data.get("content_meta", {})
        publish_time = meta.get("created_time")

        # created_at 须为 ISO 8601 格式
        created_at_iso = None
        if isinstance(publish_time, datetime):
            created_at_iso = publish_time.isoformat()
        else:
            created_at_iso = datetime.now().isoformat()

        # 内容体裁推断
        sub_type = meta.get("sub_type", "")
        answer_type = meta.get("answer_type", "")
        content_category = f"{sub_type}/{answer_type}" if answer_type else sub_type

        # 是否视频
        is_video = meta.get("is_video_answer", 0)

        return {
            # ═══════ 1. 基础元数据 ═══════
            "post_id": str(meta.get("content_id", "")),
            "author_id": "",
            "platform": platform,
            "created_at": created_at_iso,
            "timezone": "Asia/Shanghai",
            "is_reply": sub_type == "comment",
            "is_quote_tweet": False,
            "is_retweet": False,
            "reply_to_id": None,
            "content_category": content_category,

            # ═══════ 2. 内容特征（核心） ═══════
            "content_features": content_features,

            # ═══════ 3. 表现反馈 ═══════
            "performance_feedback": performance_feedback,

            # ═══════ 4. 发布上下文 ═══════
            "context": context,

            # ═══════ 5. 自学习辅助标记 ═══════
            "learning_tags": {
                "is_hit": False,
                "is_low_effect": False,
                "sample_weight": 1.0,
            },

            # ═══════ 6. 采集元信息 ═══════
            "crawl_meta": {
                "crawl_time": datetime.now().isoformat(),
                "generate_type": "ai_auto",
                "is_video": bool(is_video),
                "content_status": platform_data.get("advanced", {}).get("status", "normal"),
            },
        }


async def test_collect():
    """测试知乎数据采集与完整 schema 输出"""
    collector = ContentMetricsCollector()
    metrics = await collector.collect_content_metrics("2016869402193175389", "zhihu")
    print(json.dumps(metrics, indent=2, ensure_ascii=False, default=str))
    return metrics


if __name__ == "__main__":
    asyncio.run(test_collect())
