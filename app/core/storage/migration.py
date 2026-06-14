"""
数据库迁移 — 维护 SCHEMA_VERSION 和所有建表 DDL

版本策略：
  - 每增加一个版本在 _MIGRATIONS 中添加一个 (version, sql) 元组
  - init 时按顺序执行未应用的迁移
  - 严禁修改已发布版本的 SQL，只能追加新版本
"""

from __future__ import annotations
from typing import List, Tuple
from app.core.config_manager import config
from app.tools.logging_config import LoggingConfig

# ── 当前 schema 版本 ──
CURRENT_VERSION = 1

# ── 所有迁移：[(version, SQL), ...] ──
_MIGRATIONS: List[Tuple[int, str]] = [
    (
        1,
        """
        -- ============================
        -- V1: 初始建表
        -- ============================

        CREATE TABLE IF NOT EXISTS _schema_version (
            version     INTEGER PRIMARY KEY,
            applied_at  TEXT NOT NULL
        );

        -- 1. 内容主表
        CREATE TABLE IF NOT EXISTS contents (
            id              TEXT PRIMARY KEY,
            platform        TEXT NOT NULL,
            publish_type    TEXT NOT NULL,
            title           TEXT NOT NULL,
            content         TEXT NOT NULL,
            content_plain   TEXT,
            hot_topic_title TEXT,
            hot_topic_url   TEXT,
            hot_topic_rank  INTEGER,
            status          TEXT NOT NULL DEFAULT 'draft',
            platform_url    TEXT,
            quality_score   REAL,
            quality_report  TEXT,
            model_name      TEXT,
            prompt_id       TEXT,
            token_count     INTEGER,
            iteration_round INTEGER DEFAULT 1,
            created_at      TEXT NOT NULL,
            published_at    TEXT,
            updated_at      TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_contents_platform
            ON contents(platform);
        CREATE INDEX IF NOT EXISTS idx_contents_status
            ON contents(status);
        CREATE INDEX IF NOT EXISTS idx_contents_created
            ON contents(created_at);
        CREATE INDEX IF NOT EXISTS idx_contents_platform_status
            ON contents(platform, status);

        -- 2. 平台表现数据
        CREATE TABLE IF NOT EXISTS performance_metrics (
            id                  TEXT PRIMARY KEY,
            content_id          TEXT NOT NULL REFERENCES contents(id),
            platform            TEXT NOT NULL,
            impressions         INTEGER DEFAULT 0,
            likes               INTEGER DEFAULT 0,
            comments            INTEGER DEFAULT 0,
            shares              INTEGER DEFAULT 0,
            bookmarks           INTEGER DEFAULT 0,
            followers_gained    INTEGER DEFAULT 0,
            engagement_rate     REAL DEFAULT 0.0,
            raw_data            TEXT,
            collected_at        TEXT NOT NULL,
            UNIQUE(content_id, collected_at)
        );

        CREATE INDEX IF NOT EXISTS idx_metrics_content
            ON performance_metrics(content_id);
        CREATE INDEX IF NOT EXISTS idx_metrics_platform
            ON performance_metrics(platform);

        -- 3. 自学习分析记录
        CREATE TABLE IF NOT EXISTS learning_records (
            id                  TEXT PRIMARY KEY,
            content_id          TEXT NOT NULL UNIQUE REFERENCES contents(id),
            platform            TEXT NOT NULL,
            surface_text        TEXT,
            hook_and_structure  TEXT,
            language_style      TEXT,
            topic_and_semantics TEXT,
            multimedia          TEXT,
            context             TEXT,
            learning_tags       TEXT,
            created_at          TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_learning_content
            ON learning_records(content_id);
        CREATE INDEX IF NOT EXISTS idx_learning_platform
            ON learning_records(platform);

        -- 4. 发布日志
        CREATE TABLE IF NOT EXISTS publish_logs (
            id              TEXT PRIMARY KEY,
            content_id      TEXT NOT NULL REFERENCES contents(id),
            platform        TEXT NOT NULL,
            action          TEXT NOT NULL,
            status          TEXT NOT NULL,
            error_message   TEXT,
            duration_ms     INTEGER,
            created_at      TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_publish_log_content
            ON publish_logs(content_id);

        -- 5. 热榜监控事件
        CREATE TABLE IF NOT EXISTS monitor_events (
            id              TEXT PRIMARY KEY,
            platform        TEXT NOT NULL,
            title           TEXT NOT NULL,
            rank            INTEGER,
            url             TEXT,
            hot_score       TEXT,
            action          TEXT NOT NULL,
            content_id      TEXT REFERENCES contents(id),
            detected_at     TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_monitor_platform
            ON monitor_events(platform);
        CREATE INDEX IF NOT EXISTS idx_monitor_detected
            ON monitor_events(detected_at);

        -- 6. 风格锚点
        CREATE TABLE IF NOT EXISTS style_anchors (
            id                  TEXT PRIMARY KEY,
            platform            TEXT NOT NULL,
            name                TEXT NOT NULL,
            content             TEXT NOT NULL,
            tags                TEXT,
            hook_type           TEXT,
            structure_type      TEXT,
            effectiveness_score REAL DEFAULT 0.0,
            source              TEXT NOT NULL DEFAULT 'manual',
            usage_count         INTEGER DEFAULT 0,
            created_at          TEXT NOT NULL,
            updated_at          TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_style_platform
            ON style_anchors(platform);
        """,
    ),
]


async def run_migrations(db) -> None:
    """
    执行所有未应用的迁移

    参数 db: aiosqlite.Connection
    """
    from datetime import datetime

    logger = LoggingConfig(log_file_path=config.logfile_path, log_level=config.log_level).get_logger(
        f"{__name__}")

    # 确保版本表存在
    await db.execute("""
        CREATE TABLE IF NOT EXISTS _schema_version (
            version     INTEGER PRIMARY KEY,
            applied_at  TEXT NOT NULL
        )
    """)
    await db.commit()

    cursor = await db.execute(
        "SELECT COALESCE(MAX(version), 0) FROM _schema_version"
    )
    row = await cursor.fetchone()
    current_ver = row[0] if row else 0

    for version, sql in _MIGRATIONS:
        if version > current_ver:
            logger.info(f"📦 执行数据库迁移 V{version} ...")
            await db.executescript(sql)
            await db.execute(
                "INSERT INTO _schema_version (version, applied_at) VALUES (?, ?)",
                (version, datetime.now().isoformat()),
            )
            await db.commit()
            logger.info(f"✅ 迁移 V{version} 完成")
