"""
数据模型 - 定义所有存储记录的数据类

所有字段与 database schema 一一对应，
JSON 字段在 Python 侧用 str 表示（入库前自行 json.dumps），
保持灵活性避免强依赖序列化库。
"""

from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime


def _now_iso() -> str:
    """返回当前时间的 ISO 格式字符串"""
    return datetime.now().isoformat()


def _new_id() -> str:
    """生成新的唯一 ID"""
    import uuid
    return uuid.uuid4().hex


# ==================== 1. 内容主表 ====================
@dataclass
class ContentRecord:
    """生成的内容记录"""
    id: str = field(default_factory=_new_id)
    platform: str = ""
    publish_type: str = ""
    title: str = ""
    content: str = ""
    content_plain: Optional[str] = None
    hot_topic_title: Optional[str] = None
    hot_topic_url: Optional[str] = None
    hot_topic_rank: Optional[int] = None
    status: str = "draft"  # draft|generated|published|failed
    platform_url: Optional[str] = None
    quality_score: Optional[float] = None
    quality_report: Optional[str] = None  # JSON
    model_name: Optional[str] = None
    prompt_id: Optional[str] = None
    token_count: Optional[int] = None
    iteration_round: int = 1
    created_at: str = field(default_factory=_now_iso)
    published_at: Optional[str] = None
    updated_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict:
        return asdict(self)


# ==================== 2. 平台表现数据 ====================
@dataclass
class PerformanceRecord:
    """从平台采集的表现指标"""
    id: str = field(default_factory=_new_id)
    content_id: str = ""
    platform: str = ""
    impressions: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    bookmarks: int = 0
    followers_gained: int = 0
    engagement_rate: float = 0.0
    raw_data: Optional[str] = None  # 原始 API 响应 JSON
    collected_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict:
        return asdict(self)


# ==================== 3. 自学习分析记录 ====================
@dataclass
class LearningRecord:
    """NLP + LLM 分析结果"""
    id: str = field(default_factory=_new_id)
    content_id: str = ""
    platform: str = ""
    surface_text: Optional[str] = None  # JSON
    hook_and_structure: Optional[str] = None  # JSON
    language_style: Optional[str] = None  # JSON
    topic_and_semantics: Optional[str] = None  # JSON
    multimedia: Optional[str] = None  # JSON
    context: Optional[str] = None  # JSON
    learning_tags: Optional[str] = None  # JSON
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict:
        return asdict(self)


# ==================== 4. 发布日志 ====================
@dataclass
class PublishLogRecord:
    """发布操作的详细日志"""
    id: str = field(default_factory=_new_id)
    content_id: str = ""
    platform: str = ""
    action: str = ""  # publish|retry|rollback
    status: str = ""  # success|failure
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict:
        return asdict(self)


# ==================== 5. 热榜监控事件 ====================
@dataclass
class MonitorEventRecord:
    """热榜变化事件"""
    id: str = field(default_factory=_new_id)
    platform: str = ""
    title: str = ""
    rank: Optional[int] = None
    url: Optional[str] = None
    hot_score: Optional[str] = None
    action: str = ""  # new|changed|published|skipped
    content_id: Optional[str] = None
    detected_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict:
        return asdict(self)


# ==================== 6. 风格锚点 ====================
@dataclass
class StyleAnchorRecord:
    """写作风格参考样本"""
    id: str = field(default_factory=_new_id)
    platform: str = ""
    name: str = ""
    content: str = ""
    tags: Optional[str] = None  # JSON 数组
    hook_type: Optional[str] = None
    structure_type: Optional[str] = None
    effectiveness_score: float = 0.0
    source: str = "manual"  # manual|auto_extracted|learning
    usage_count: int = 0
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict:
        return asdict(self)
