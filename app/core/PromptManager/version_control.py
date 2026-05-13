"""
提示词版本控制模块

功能：
- 保存版本快照 (save_snapshot)
- 获取历史版本 (get_version)
- 列出所有版本 (list_versions)
- 版本对比差异 (diff)

存储结构：
prompts_history/
└── {prompt_id}/
    ├── manifest.json              # 版本索引清单
    ├── v_20260513_100000.json     # 版本快照(完整 Prompt 对象)
    └── v_20260513_143022.json
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from difflib import unified_diff
from typing import Optional

from app.tools.LoggingConfig import LoggingConfig
from app.core.config_manager import config
from .models import Prompt, VersionRecord, ChangeInfo, DiffResult


class PromptVersionControl:
    """提示词版本控制（类似 Git 的轻量实现）"""

    def __init__(self):
        self.log = LoggingConfig(
            log_file_path=config.logfile_path,
            log_level=config.log_level,
        ).get_logger(self.__class__.__name__)

        # 基础路径：app/prompts_history/
        self.base_dir = Path(__file__).parent.parent.parent / "prompts_history"

    # ------------------------------------------------------------------ #
    #  公共接口
    # ------------------------------------------------------------------ #
    def save_snapshot(self, prompt: Prompt, change_info: ChangeInfo) -> VersionRecord:
        """
        保存版本快照

        流程：
        1. 生成 version_id (时间戳格式)
        2. 将完整 Prompt 序列化为 JSON 写入 history 目录
        3. 更新 manifest.json 索引
        4. 返回版本记录

        Args:
            prompt: 要保存的完整提示词对象
            change_info: 本次变更信息

        Returns:
            VersionRecord: 版本记录
        """
        now = datetime.now(timezone.utc)
        timestamp_str = now.strftime("%Y%m%d_%H%M%S")
        version_id = f"v_{timestamp_str}"

        # 目标目录
        prompt_history_dir = self.base_dir / prompt.id
        snapshot_file = prompt_history_dir / f"{version_id}.json"
        manifest_file = prompt_history_dir / "manifest.json"

        # 创建目录
        os.makedirs(prompt_history_dir, exist_ok=True)

        # ---- 1. 写入版本快照 ----
        snapshot_data = prompt.to_dict()
        with open(snapshot_file, "w", encoding="utf-8") as f:
            json.dump(snapshot_data, f, ensure_ascii=False, indent=2)

        self.log.info(f"[VersionControl] 已保存快照: {snapshot_file}")

        # ---- 2. 更新 manifest ----
        record = VersionRecord(
            version_id=version_id,
            timestamp=now.isoformat(),
            version=prompt.version,
            change_type=change_info.change_type,
            change_reason=change_info.change_reason,
            source=change_info.source,
            parent=self._get_latest_version_id(prompt.id),
            file_path=str(snapshot_file),
        )

        # 读取已有 manifest 或创建新的
        manifest = self._load_manifest(prompt.id)
        if "versions" not in manifest:
            manifest["versions"] = []
        manifest["versions"].append(record.to_dict())
        manifest["prompt_id"] = prompt.id

        # 保存 manifest
        with open(manifest_file, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        self.log.info(
            f"[VersionControl] manifest 已更新: {prompt.id} -> "
            f"{version_id} ({change_info.change_type})"
        )

        return record

    def get_version(self, prompt_id: str, version_id: str) -> Optional[Prompt]:
        """
        获取指定历史版本的完整内容

        Args:
            prompt_id: 提示词 ID
            version_id: 版本 ID, 如 "v_20260513_143022"

        Returns:
            Prompt 对象, 不存在则返回 None
        """
        snapshot_file = self.base_dir / prompt_id / f"{version_id}.json"
        if not snapshot_file.exists():
            self.log.warning(f"[VersionControl] 版本快照不存在: {snapshot_file}")
            return None

        try:
            with open(snapshot_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Prompt.from_dict(data)
        except Exception as e:
            self.log.error(f"[VersionControl] 读取快照失败: {e}")
            return None

    def list_versions(self, prompt_id: str) -> list[VersionRecord]:
        """
        列出某提示词的所有历史版本 (按时间正序)

        Returns:
            版本记录列表, 无记录则返回空列表
        """
        manifest = self._load_manifest(prompt_id)
        versions_raw = manifest.get("versions", [])

        return [VersionRecord.from_dict(v) for v in versions_raw]

    def diff(self, prompt_id: str, from_ver: str, to_ver: str) -> Optional[DiffResult]:
        """
        生成两个版本之间的文本差异

        Args:
            prompt_id: 提示词 ID
            from_ver: 基准版本 ID
            to_ver: 对比版本 ID

        Returns:
            DiffResult, 任一版本不存在则返回 None
        """
        from_prompt = self.get_version(prompt_id, from_ver)
        to_prompt = self.get_version(prompt_id, to_ver)

        if from_prompt is None or to_prompt is None:
            self.log.warning("[VersionControl] diff 失败: 版本不存在")
            return None

        from_lines = from_prompt.content.splitlines(keepends=True)
        to_lines = to_prompt.content.splitlines(keepends=True)

        # 使用 unified_diff 生成差异
        diff_lines = list(unified_diff(
            from_lines, to_lines,
            fromfile=f"v{from_ver} (v{from_prompt.version})",
            tofile=f"v{to_ver} (v{to_prompt.version})",
            lineterm="",
        ))

        additions = []
        deletions = []

        for line in diff_lines:
            if line.startswith('+') and not line.startswith('+++'):
                additions.append(line[1:])  # 去掉前缀 +
            elif line.startswith('-') and not line.startswith('---'):
                deletions.append(line[1:])  # 去掉前缀 -

        summary = (
            f"从 v{from_ver}({from_prompt.version}) → "
            f"v{to_ver}({to_prompt.version}): "
            f"+{len(additions)} 行 / -{len(deletions)} 行"
        )

        return DiffResult(
            from_version_id=from_ver,
            to_version_id=to_ver,
            from_content=from_prompt.content,
            to_content=to_prompt.content,
            additions=additions,
            deletions=deletions,
            changes_summary=summary,
        )

    def get_latest_version(self, prompt_id: str) -> Optional[VersionRecord]:
        """获取最新的一条版本记录"""
        versions = self.list_versions(prompt_id)
        return versions[-1] if versions else None

    # ------------------------------------------------------------------ #
    #  私有方法
    # ------------------------------------------------------------------ #
    def _load_manifest(self, prompt_id: str) -> dict:
        """加载 manifest.json, 不存在返回空字典"""
        manifest_file = self.base_dir / prompt_id / "manifest.json"
        if not manifest_file.exists():
            return {}
        try:
            with open(manifest_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.log.warning(f"[VersionControl] 加载 manifest 失败: {e}")
            return {}

    def _get_latest_version_id(self, prompt_id: str) -> Optional[str]:
        """获取当前最新版本的 ID (作为 parent)"""
        latest = self.get_latest_version(prompt_id)
        return latest.version_id if latest else None
