"""
数据模型自定义
"""

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Prompt:
    """单个提示词数据模型"""
    id: str  # 唯一标识, 如 "zhihu_answer"
    name: str  # 显示名称
    platform: str  # 所属平台 "zhihu" / "weibo"
    category: str = "content_creation"  # 分类
    version: str = "1.0.0"  # 语义化版本号
    created_at: str = ""  # ISO 时间戳 (创建时自动生成)
    updated_at: str = ""  # 最后更新时间
    author: str = "system"  # 创建者 "system" / "user" / "ai"
    tags: list[str] = field(default_factory=list)  # 标签列表
    variables: list[dict] = field(default_factory=list)  # 模板变量定义
    content: str = ""  # 提示词正文
    metadata: dict = field(default_factory=dict)  # 扩展元数据

    def to_dict(self) -> dict:
        """将数据模型转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Prompt":
        """从字典创建数据模型实例"""
        return cls(**data)


@dataclass
class VersionRecord:
    """一条版本记录"""
    version_id: str  # 如 "v_20260513_143022"
    timestamp: str  # ISO 时间戳
    version: str  # 语义版本号 "1.5.0"
    change_type: str  # "initial" / "manual" / "ai_optimized" / "rollback"
    change_reason: str  # 变更原因描述
    source: str  # "user_edit" / "ai_optimizer" / "migration"
    parent: Optional[str] = None  # 父版本 ID (用于构建版本链)
    file_path: str = ""  # 快照文件路径

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'VersionRecord':
        return cls(**data)


@dataclass
class ChangeInfo:
    """变更信息（传参用）"""
    change_type: str = "manual"  # 变更类型
    change_reason: str = ""  # 变更原因
    source: str = "user_edit"  # 来源


@dataclass
class DiffResult:
    """版本对比结果"""
    from_version_id: str
    to_version_id: str
    from_content: str
    to_content: str
    additions: list[str] = field(default_factory=list)  # 新增行
    deletions: list[str] = field(default_factory=list)  # 删除行
    changes_summary: str = ""  # 变更摘要
