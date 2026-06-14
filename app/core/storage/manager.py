"""
AsyncStorageManager — 异步存储管理器

三层职责：
  1. 管理 SQLite 连接生命周期（初始化/迁移/关闭）
  2. 提供统一的 CRUD 接口供业务层调用
  3. 屏蔽底层数据库差异（预留 MySQL 切换能力）

用法：
    from app.core.storage import storage

    # 初始化（应用启动时）
    await storage.initialize("./Data/ai_blogger.db")

    # 写入
    record = ContentRecord(platform="zhihu", title="...", content="...")
    await storage.save_content(record)

    # 查询
    results = await storage.query_contents(platform="zhihu", status="published")

    # 关闭（应用退出时）
    await storage.close()
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Union, Dict, Any

from app.core.storage.models import (
    ContentRecord,
    PerformanceRecord,
    LearningRecord,
    PublishLogRecord,
    MonitorEventRecord,
    StyleAnchorRecord,
)
from app.core.storage.migration import CURRENT_VERSION, run_migrations

from app.core.config_manager import config
from app.tools.logging_config import LoggingConfig


class AsyncStorageManager:
    """异步存储管理器 — 全局单例，统一管理结构化数据"""

    def __init__(self):
        self._db = None
        self._initialized = False
        self._db_path: Optional[Path] = None

        self.log = LoggingConfig(log_file_path=config.logfile_path, log_level=config.log_level).get_logger(
            f"{self.__class__.__name__}")

    # ── 生命周期 ───────────────────────────────────────
    async def initialize(
            self, db_path: Union[str, Path], auto_migrate: bool = True
    ) -> None:
        """
        初始化数据库连接

        Args:
            db_path: SQLite 文件路径
            auto_migrate: 是否自动执行迁移
        """
        if self._initialized:
            self.log.warning("存储层已初始化，跳过重复初始化")
            return

        import aiosqlite

        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path

        self._db = await aiosqlite.connect(str(db_path))
        self._db.row_factory = aiosqlite.Row

        # SQLite 性能优化
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")
        await self._db.execute("PRAGMA busy_timeout=5000")

        if auto_migrate:
            await run_migrations(self._db)

        self._initialized = True
        self.log.info(f"✅ 存储层初始化完成: {db_path}")

    async def close(self) -> None:
        """关闭数据库连接"""
        if self._db and self._initialized:
            await self._db.close()
            self._db = None
            self._initialized = False
            self.log.info("✅ 存储层已关闭")

    @property
    def is_initialized(self) -> bool:
        """是否已初始化"""
        return self._initialized

    # ── 内部工具 ───────────────────────────────────────
    async def _execute(self, sql: str, params: tuple = ()) -> Any:
        """执行 SQL 并返回 cursor"""
        return await self._db.execute(sql, params)

    async def _execute_insert(self, sql: str, params: tuple) -> None:
        """执行插入并提交"""
        await self._db.execute(sql, params)
        await self._db.commit()

    async def _fetchone(self, sql: str, params: tuple = ()) -> Optional[dict]:
        cursor = await self._db.execute(sql, params)
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def _fetchall(self, sql: str, params: tuple = ()) -> List[dict]:
        cursor = await self._db.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    # ====================================================
    #  内容管理
    # ====================================================
    async def save_content(self, record: ContentRecord) -> str:
        """保存内容记录，返回 content_id"""
        await self._execute_insert(
            """INSERT INTO contents (
                id, platform, publish_type, title, content, content_plain,
                hot_topic_title, hot_topic_url, hot_topic_rank,
                status, platform_url,
                quality_score, quality_report,
                model_name, prompt_id, token_count, iteration_round,
                created_at, published_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.id, record.platform, record.publish_type,
                record.title, record.content, record.content_plain,
                record.hot_topic_title, record.hot_topic_url,
                record.hot_topic_rank,
                record.status, record.platform_url,
                record.quality_score, record.quality_report,
                record.model_name, record.prompt_id,
                record.token_count, record.iteration_round,
                record.created_at, record.published_at, record.updated_at,
            ),
        )
        self.log.debug(f"💾 内容已保存: {record.id[:8]}... ({record.platform})")
        return record.id

    async def get_content(self, content_id: str) -> Optional[ContentRecord]:
        """按 ID 获取内容"""
        row = await self._fetchone(
            "SELECT * FROM contents WHERE id = ?", (content_id,)
        )
        return ContentRecord(**row) if row else None

    async def update_content_status(
            self, content_id: str, status: str, **extra
    ) -> bool:
        """
        更新内容状态

        Args:
            content_id: 内容 ID
            status: 新状态
            **extra: 其他更新字段（platform_url, quality_score 等）
        """
        now = datetime.now().isoformat()
        set_parts = ["status = ?", "updated_at = ?"]
        params: list = [status, now]

        if status == "published":
            set_parts.append("published_at = ?")
            params.append(now)

        for key, value in extra.items():
            if key in (
                    "platform_url", "quality_score", "quality_report",
                    "model_name", "prompt_id", "token_count", "iteration_round",
                    "content_plain",
            ):
                set_parts.append(f"{key} = ?")
                params.append(value)

        params.append(content_id)
        sql = f"UPDATE contents SET {', '.join(set_parts)} WHERE id = ?"
        await self._execute_insert(sql, tuple(params))
        return True

    async def query_contents(
            self,
            platform: Optional[str] = None,
            status: Optional[str] = None,
            start_date: Optional[str] = None,
            end_date: Optional[str] = None,
            sort_by: str = "created_at",
            sort_dir: str = "DESC",
            limit: int = 50,
            offset: int = 0,
    ) -> List[ContentRecord]:
        """
        灵活查询内容列表

        用法示例:
            # 知乎上周发布的文章
            records = await storage.query_contents(
                platform="zhihu", status="published",
                start_date="2026-06-07", end_date="2026-06-14"
            )
        """
        conditions: list[str] = []
        params: list = []

        if platform:
            conditions.append("platform = ?")
            params.append(platform)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if start_date:
            conditions.append("created_at >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("created_at <= ?")
            params.append(end_date)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        # 排序方向安全校验
        sort_dir = sort_dir.upper()
        if sort_dir not in ("ASC", "DESC"):
            sort_dir = "DESC"
        # sort_by 使用白名单防止注入
        _allowed_sort = {
            "created_at", "updated_at", "published_at",
            "quality_score", "platform",
        }
        if sort_by not in _allowed_sort:
            sort_by = "created_at"

        sql = (
            f"SELECT * FROM contents {where} "
            f"ORDER BY {sort_by} {sort_dir} "
            f"LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])

        rows = await self._fetchall(sql, tuple(params))
        return [ContentRecord(**r) for r in rows]

    async def count_contents(
            self,
            platform: Optional[str] = None,
            status: Optional[str] = None,
    ) -> int:
        """统计内容数量"""
        conditions = []
        params = []
        if platform:
            conditions.append("platform = ?")
            params.append(platform)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        row = await self._fetchone(
            f"SELECT COUNT(*) as cnt FROM contents {where}", tuple(params)
        )
        return row["cnt"] if row else 0

    # ====================================================
    #  平台表现数据
    # ====================================================

    async def save_performance(self, record: PerformanceRecord) -> str:
        """保存平台表现数据"""
        await self._execute_insert(
            """INSERT OR REPLACE INTO performance_metrics (
                id, content_id, platform,
                impressions, likes, comments, shares, bookmarks,
                followers_gained, engagement_rate, raw_data, collected_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.id, record.content_id, record.platform,
                record.impressions, record.likes, record.comments,
                record.shares, record.bookmarks, record.followers_gained,
                record.engagement_rate, record.raw_data, record.collected_at,
            ),
        )
        return record.id

    async def get_performance(
            self, content_id: str
    ) -> List[PerformanceRecord]:
        """获取某条内容的所有历史表现数据"""
        rows = await self._fetchall(
            "SELECT * FROM performance_metrics WHERE content_id = ? ORDER BY collected_at DESC",
            (content_id,),
        )
        return [PerformanceRecord(**r) for r in rows]

    async def get_top_performing(
            self,
            platform: str,
            metric: str = "engagement_rate",
            days: int = 7,
            limit: int = 10,
    ) -> List[dict]:
        """
        查询表现最佳的内容（自学习核心接口）

        Args:
            platform: 平台
            metric: 排序指标 (engagement_rate|likes|impressions|comments)
            days: 最近 N 天
            limit: 返回条数

        Returns:
            [ {content_id, title, platform, metric_value, ...}, ... ]
        """
        _allowed_metrics = {
            "engagement_rate", "likes", "impressions", "comments",
            "shares", "bookmarks",
        }
        if metric not in _allowed_metrics:
            metric = "engagement_rate"

        from datetime import timedelta

        since = (datetime.now() - timedelta(days=days)).isoformat()

        rows = await self._fetchall(
            f"""SELECT c.id as content_id, c.title, c.platform,
                       p.{metric} as metric_value,
                       p.impressions, p.likes, p.comments,
                       p.collected_at
                FROM performance_metrics p
                JOIN contents c ON c.id = p.content_id
                WHERE c.platform = ? AND p.collected_at >= ?
                ORDER BY p.{metric} DESC
                LIMIT ?""",
            (platform, since, limit),
        )
        return rows

    # ====================================================
    #  自学习记录
    # ====================================================

    async def save_learning_record(self, record: LearningRecord) -> str:
        """保存自学习分析记录"""
        await self._execute_insert(
            """INSERT OR REPLACE INTO learning_records (
                id, content_id, platform,
                surface_text, hook_and_structure, language_style,
                topic_and_semantics, multimedia, context,
                learning_tags, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.id, record.content_id, record.platform,
                record.surface_text, record.hook_and_structure,
                record.language_style, record.topic_and_semantics,
                record.multimedia, record.context,
                record.learning_tags, record.created_at,
            ),
        )
        return record.id

    async def get_learning_record(
            self, content_id: str
    ) -> Optional[LearningRecord]:
        """获取某条内容的学习分析记录"""
        row = await self._fetchone(
            "SELECT * FROM learning_records WHERE content_id = ?",
            (content_id,),
        )
        return LearningRecord(**row) if row else None

    async def get_learning_insights(
            self,
            platform: str,
            min_engagement: float = 0.0,
            limit: int = 20,
    ) -> List[dict]:
        """
        自学习洞察：聚合分析"什么特征的内容效果好"

        返回每个内容的特征 + 表现数据，供 LLM 分析模式

        Returns:
            [{
                content_id, title,
                hook_and_structure: {hook_type, structure_type, ...},
                language_style: {sentiment_polarity, ...},
                engagement_rate, likes, impressions, ...
            }, ...]
        """
        rows = await self._fetchall(
            """SELECT
                   c.id as content_id, c.title,
                   lr.hook_and_structure, lr.language_style,
                   lr.topic_and_semantics, lr.surface_text,
                   p.engagement_rate, p.likes, p.impressions, p.comments
                FROM learning_records lr
                JOIN contents c ON c.id = lr.content_id
                JOIN performance_metrics p ON p.content_id = c.id
                WHERE c.platform = ? AND p.engagement_rate >= ?
                ORDER BY p.engagement_rate DESC
                LIMIT ?""",
            (platform, min_engagement, limit),
        )
        # JSON 字段自动解析
        result = []
        for row in rows:
            d = dict(row)
            for key in (
                    "hook_and_structure", "language_style",
                    "topic_and_semantics", "surface_text",
            ):
                if isinstance(d.get(key), str):
                    try:
                        d[key] = json.loads(d[key])
                    except (json.JSONDecodeError, TypeError):
                        pass
            result.append(d)
        return result

    # ====================================================
    #  发布日志
    # ====================================================

    async def log_publish(self, record: PublishLogRecord) -> str:
        """记录发布操作"""
        await self._execute_insert(
            """INSERT INTO publish_logs (
                id, content_id, platform, action, status,
                error_message, duration_ms, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.id, record.content_id, record.platform,
                record.action, record.status,
                record.error_message, record.duration_ms, record.created_at,
            ),
        )
        return record.id

    async def get_publish_history(
            self, content_id: str
    ) -> List[PublishLogRecord]:
        """获取发布历史"""
        rows = await self._fetchall(
            "SELECT * FROM publish_logs WHERE content_id = ? ORDER BY created_at",
            (content_id,),
        )
        return [PublishLogRecord(**r) for r in rows]

    # ====================================================
    #  热榜监控事件
    # ====================================================

    async def log_monitor_event(self, record: MonitorEventRecord) -> str:
        """记录热榜监控事件"""
        await self._execute_insert(
            """INSERT INTO monitor_events (
                id, platform, title, rank, url, hot_score,
                action, content_id, detected_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.id, record.platform, record.title, record.rank,
                record.url, record.hot_score, record.action,
                record.content_id, record.detected_at,
            ),
        )
        return record.id

    async def get_recent_monitor_events(
            self, platform: str, limit: int = 50
    ) -> List[MonitorEventRecord]:
        """获取最近的监控事件"""
        rows = await self._fetchall(
            "SELECT * FROM monitor_events WHERE platform = ? ORDER BY detected_at DESC LIMIT ?",
            (platform, limit),
        )
        return [MonitorEventRecord(**r) for r in rows]

    # ====================================================
    #  风格锚点
    # ====================================================

    async def save_style_anchor(self, record: StyleAnchorRecord) -> str:
        """保存风格锚点"""
        await self._execute_insert(
            """INSERT OR REPLACE INTO style_anchors (
                id, platform, name, content, tags,
                hook_type, structure_type,
                effectiveness_score, source, usage_count,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.id, record.platform, record.name, record.content,
                record.tags, record.hook_type, record.structure_type,
                record.effectiveness_score, record.source, record.usage_count,
                record.created_at, record.updated_at,
            ),
        )
        return record.id

    async def get_effective_styles(
            self,
            platform: str,
            min_score: float = 7.0,
            limit: int = 10,
    ) -> List[StyleAnchorRecord]:
        """获取效果最好的风格（供自学习回写 Writer）"""
        rows = await self._fetchall(
            "SELECT * FROM style_anchors WHERE platform = ? AND effectiveness_score >= ? ORDER BY effectiveness_score DESC LIMIT ?",
            (platform, min_score, limit),
        )
        return [StyleAnchorRecord(**r) for r in rows]

    # ====================================================
    #  统计看板
    # ====================================================

    async def get_dashboard_stats(self) -> Dict[str, Any]:
        """系统概览统计"""
        total = await self.count_contents()
        published = await self.count_contents(status="published")
        failed = await self.count_contents(status="failed")

        row = await self._fetchone(
            "SELECT COALESCE(AVG(engagement_rate), 0) as avg_engagement FROM performance_metrics"
        )
        avg_engagement = row["avg_engagement"] if row else 0.0

        row = await self._fetchone(
            "SELECT COUNT(DISTINCT platform) as platform_count FROM contents"
        )
        platform_count = row["platform_count"] if row else 0

        return {
            "total_contents": total,
            "published": published,
            "failed": failed,
            "platform_count": platform_count,
            "avg_engagement_rate": round(avg_engagement, 4),
            "db_path": str(self._db_path) if self._db_path else None,
        }
