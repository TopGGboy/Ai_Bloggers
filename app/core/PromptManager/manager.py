"""
PromptManager - 提示词统一管理入口

核心职责：
1. 从 prompts/*.json 加载提示词 (支持自定义覆盖优先级)
2. 提供增删改查接口
3. 协调版本控制模块自动存档
4. 提供历史查询和回退能力

目录结构：
app/prompts/
├── registry.json           # 全局注册表
├── zhihu/
│   ├── answer.json
│   └── article.json
├── weibo/
│   └── article.json
└── custom/                 # 用户自定义覆盖区
    └── zhihu_answer.json   # 可选, 存在时优先使用

app/prompts_history/        # 版本快照 (由 version_control 管理)
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.tools.LoggingConfig import LoggingConfig
from app.core.config_manager import config
from app.core.PromptManager.models import Prompt, VersionRecord, ChangeInfo, DiffResult
from app.core.PromptManager.version_control import PromptVersionControl


class PromptManager:
    """提示词统一管理器 — 全局单例入口"""

    def __init__(self):
        self.log = LoggingConfig(
            log_file_path=config.logfile_path,
            log_level=config.log_level,
        ).get_logger(self.__class__.__name__)

        # ---- 目录定位 ----
        self.app_base = Path(__file__).parent.parent.parent  # app/
        self.prompts_dir = self.app_base / "prompts"  # app/prompts/
        self.history_dir = self.app_base / "prompts_history"  # app/prompts_history/
        self.custom_dir = self.prompts_dir / "custom"  # app/prompts/custom/
        self.registry_file = self.prompts_dir / "registry.json"  # app/prompts/registry.json

        # ---- 子系统 ----
        self.version_control = PromptVersionControl()

        # ---- 缓存 ----
        self._cache: dict[str, Prompt] = {}

        # 初始化目录
        self._ensure_dirs()

        self.log.info("[PromptManager] 初始化完成")

    # ================================================================== #
    #   核心读取
    # ================================================================== #

    def get_prompt(self, prompt_id: str) -> Prompt:
        """
        获取提示词 (优先级: custom > default)

        加载策略：
        1. 检查缓存
        2. 检查自定义覆盖: prompts/custom/{prompt_id}.json
        3. 检查默认位置: 通过 registry.json 查找对应文件路径
        4. 都找不到则抛出明确错误

        Args:
            prompt_id: 提示词唯一标识, 如 "zhihu_answer"

        Returns:
            Prompt 对象

        Raises:
            FileNotFoundError: 提示词文件不存在
        """
        # 缓存命中
        if prompt_id in self._cache:
            cached = self._cache[prompt_id]
            # 自定义文件可能被外部修改, 每次检查 custom 是否更新
            if cached.metadata.get("_is_custom", False):
                custom_file = self.custom_dir / f"{prompt_id}.json"
                if custom_file.exists():
                    mtime = os.path.getmtime(custom_file)
                    if cached.metadata.get("_custom_mtime", 0) != mtime:
                        self.log.debug(f"[PromptManager] 检测到自定义文件变更, 重新加载: {prompt_id}")
                        return self._load_and_cache(prompt_id)
            return cached

        # 缓存未命中, 从默认位置加载
        return self._load_and_cache(prompt_id)

    def _load_and_cache(self, prompt_id: str) -> Prompt:
        """内部: 加载并缓存"""
        prompt = self._do_load(prompt_id)
        self._cache[prompt_id] = prompt

        # ---- 首次加载时自动创建初始快照 (确保 rollback 有 v_initial 可用) ----
        existing_versions = self.version_control.list_versions(prompt_id)
        if not existing_versions:
            from .models import ChangeInfo
            self.version_control.save_snapshot(
                prompt,
                change_info=ChangeInfo(
                    change_type="initial",
                    change_reason="初始版本 (从 JSON 文件迁移)",
                    source="migration",
                ),
            )
            self.log.info(f"[PromptManager] 已为 {prompt_id} 创建初始版本快照")

        # 记录使用次数
        prompt.metadata.setdefault("usage_count", 0)
        prompt.metadata["usage_count"] += 1
        prompt.metadata["last_used_at"] = datetime.now(timezone.utc).isoformat()

        return prompt

    def _do_load(self, prompt_id: str) -> Prompt:
        """
        实际加载逻辑 (不经过缓存)

        加载优先级:
          1. prompts/custom/{id}.json       — 用户自定义
          2. prompts/{platform}/{id}.json    — 运行时激活版
          3. prompts/{platform}/{id}_default.json → 出厂默认 (首次自动复制)
        """
        # ---- 1. 尝试自定义覆盖 ----
        custom_file = self.custom_dir / f"{prompt_id}.json"
        if custom_file.exists():
            self.log.info(f"[PromptManager] 加载自定义提示词: {custom_file}")
            prompt = self._load_from_file(custom_file)
            prompt.metadata["_is_custom"] = True
            prompt.metadata["_custom_mtime"] = os.path.getmtime(custom_file)
            return prompt

        # ---- 2. 通过 registry 查找默认路径 ----
        registry = self._load_registry()
        entry = registry.get("prompts", {}).get(prompt_id)

        if entry and entry.get("file"):
            active_file = self.prompts_dir / entry["file"]

            # 2a. 激活版存在 → 直接使用
            if active_file.exists():
                self.log.debug(f"[PromptManager] 加载激活版: {active_file}")
                prompt = self._load_from_file(active_file)
                prompt.metadata["_is_custom"] = False
                return prompt

            # 2b. 激活版不存在 → 尝试从 default 复制
            default_file = self._resolve_default_file(active_file)
            if default_file.exists():
                self.log.info(
                    f"[PromptManager] 激活版不存在, 从默认复制: {default_file}"
                )
                import shutil
                shutil.copy2(default_file, active_file)

                # 加载并重置版本号: default -> 1.0.0
                prompt = self._load_from_file(active_file)
                if prompt.version == "default":
                    now = datetime.now(timezone.utc).isoformat()
                    prompt.version = "1.0.0"
                    prompt.created_at = now
                    prompt.updated_at = now
                    self._save_to_file(prompt, active_file)  # 立即回写修正后的版本号
                    self.log.info(
                        f"[PromptManager] 已初始化激活版: "
                        f"{prompt_id} -> v{prompt.version}"
                    )

                prompt.metadata["_is_custom"] = False
                prompt.metadata["_copied_from_default"] = True
                return prompt

        # ---- 3. 兜底模糊搜索 ----
        found = list(self.prompts_dir.rglob(f"{prompt_id}.json"))
        for f in found:
            if "custom" not in str(f) and "prompts_history" not in str(f) and "_default" not in f.name:
                self.log.warning(f"[PromptManager] 回退到模糊搜索: {f}")
                prompt = self._load_from_file(f)
                prompt.metadata["_is_custom"] = False
                return prompt

        raise FileNotFoundError(
            f"[PromptManager] 提示词不存在: '{prompt_id}'\n"
            f"  请确认已在 prompts/ 下创建对应的 JSON 文件并在 registry.json 中注册。"
        )

    @staticmethod
    def _resolve_default_file(active_path: Path) -> Path:
        """根据激活版路径推断 default 版路径"""
        # zhihu/answer.json → zhihu/answer_default.json
        stem = active_path.stem
        return active_path.parent / f"{stem}_default{active_path.suffix}"

    # ================================================================== #
    #   列表 & 查询
    # ================================================================== #

    def list_prompts(self, filter_platform: Optional[str] = None) -> list:
        """
        列出所有可用提示词的摘要信息

        Args:
            filter_platform: 可选, 按平台过滤 ("zhihu" / "weibo")

        Returns:
            提示词摘要列表 (不含 content 正文, 减少体积)
        """
        registry = self._load_registry()
        results = []

        for pid, entry in registry.get("prompts", {}).items():
            # 平台过滤
            if filter_platform and entry.get("platform") != filter_platform:
                continue

            # 构建摘要
            summary = {
                "id": pid,
                "name": entry.get("name", ""),
                "platform": entry.get("platform", ""),
                "category": entry.get("category", ""),
                "has_custom": entry.get("has_custom", False),
                "active_version": entry.get("active_version_id", "unknown"),
            }
            results.append(summary)

        return results

    def get_history(self, prompt_id: str) -> list[VersionRecord]:
        """获取提示词的完整版本历史 (最新的在前)"""
        records = self.version_control.list_versions(prompt_id)
        # 反序: 最新的在前
        return list(reversed(records))

    def compare_versions(self, prompt_id: str, v1: str, v2: str) -> Optional[DiffResult]:
        """对比两个版本的差异"""
        return self.version_control.diff(prompt_id, v1, v2)

    # ================================================================== #
    #   写入 & 回退
    # ================================================================== #

    def update_prompt(self, prompt_id: str, content: str,
                      change_reason: str = "", source: str = "user_edit") -> Prompt:
        """
        更新提示词内容 (自动创建版本快照)

        流程：
        1. 加载当前提示词
        2. 调用 version_control.save_snapshot() 保存旧版
        3. 更新 content + version + updated_at
        4. 写回原文件
        5. 清除缓存

        Args:
            prompt_id: 提示词 ID
            content: 新的内容
            change_reason: 变更原因描述
            source: 变更来源

        Returns:
            更新后的 Prompt 对象
        """
        # ---- 1. 加载当前版本 ----
        current = self.get_prompt(prompt_id)

        # ---- 2. 保存快照 ----
        change_info = ChangeInfo(
            change_type="manual" if source == "user_edit" else source,
            change_reason=change_reason or f"内容更新 (source={source})",
            source=source,
        )
        self.version_control.save_snapshot(current, change_info)

        # ---- 3. 更新字段 ----
        current.content = content
        current.updated_at = datetime.now(timezone.utc).isoformat()
        # 自动递增补丁版本号: x.y.z -> x.y.(z+1)
        # 注意: rollback 场景由 rollback() 自行处理版本号, 此处跳过
        if source != "rollback":
            parts = current.version.split(".")
            if len(parts) == 3:
                parts[2] = str(int(parts[2]) + 1)
                current.version = ".".join(parts)

        # ---- 4. 写回文件 ----
        target_file = self._resolve_target_file(current)
        self._save_to_file(current, target_file)

        # ---- 5. 清除缓存 ----
        if prompt_id in self._cache:
            del self._cache[prompt_id]

        self.log.info(
            f"[PromptManager] 提示词已更新: {prompt_id} -> v{current.version}"
        )

        return current

    def rollback(self, prompt_id: str, version_id: str) -> Prompt:
        """
        回退到指定历史版本

        版本号规则: 使用目标版本号 + "-rb" 后缀 (revert)
        例如: rollback 到 v1.0.1 → 新版本为 v1.0.1-rb
              再次 rollback 到 v1.0.0 → 新版本为 v1.0.0-rb
        """
        # 从历史中获取旧版
        historical = self.version_control.get_version(prompt_id, version_id)
        if historical is None:
            raise ValueError(f"历史版本不存在: {version_id}")

        # ---- 构建回退专用版本号 ----
        target_version = historical.version

        # 检查是否已经对同一目标做过回退 (避免重复 -rb)
        existing_versions = self.version_control.list_versions(prompt_id)
        rb_versions = [
            r for r in existing_versions
            if r.change_type == "rollback"
               and r.version.startswith(target_version)
        ]

        if rb_versions:
            # 已有回退记录, 追加序号: v1.0.1-rb → v1.0.1-rb.2
            base = f"{target_version}-rb"
            max_suffix = 0
            for r in rb_versions:
                ver_str = r.version
                if ver_str == base:
                    max_suffix = max(max_suffix, 1)
                elif ver_str.startswith(base + "."):
                    try:
                        suffix = int(ver_str[len(base) + 1:])
                        max_suffix = max(max_suffix, suffix)
                    except ValueError:
                        pass
            new_version = f"{base}.{max_suffix + 1}"
        else:
            # 首次回退到此版本
            new_version = f"{target_version}-rb"

        self.log.info(
            f"[PromptManager] 回退 {prompt_id} 到 {version_id} "
            f"(原版 {target_version}) => 新版本号: {new_version}"
        )

        # ---- 加载当前提示词并保存快照 ----
        current = self.get_prompt(prompt_id)

        change_info = ChangeInfo(
            change_type="rollback",
            change_reason=f"回退到版本 {version_id} (原 {target_version})",
            source="rollback",
        )
        self.version_control.save_snapshot(current, change_info)

        # ---- 用历史内容替换, 手动设置版本号 ----
        current.content = historical.content
        current.updated_at = datetime.now(timezone.utc).isoformat()
        current.version = new_version

        # ---- 写回文件 ----
        target_file = self._resolve_target_file(current)
        self._save_to_file(current, target_file)

        # 清除缓存
        if prompt_id in self._cache:
            del self._cache[prompt_id]

        return current

    # ================================================================== #
    #   注册表管理
    # ================================================================== #
    def register_prompt(self, prompt: Prompt, relative_path: str):
        """
        向 registry.json 注册一个新提示词

        Args:
            prompt: 要注册的 Prompt 对象
            relative_path: 相对于 prompts/ 的路径, 如 "zhihu/answer.json"
        """
        registry = self._load_registry()
        registry.setdefault("prompts", {})[prompt.id] = {
            "file": relative_path,
            "platform": prompt.platform,
            "name": prompt.name,
            "category": prompt.category,
            "active_version_id": "initial",
            "has_custom": False,
            "custom_file": None,
        }

        # 同时确保实际 JSON 文件存在
        target = self.prompts_dir / relative_path
        os.makedirs(target.parent, exist_ok=True)
        self._save_to_file(prompt, target)

        # 写入 registry
        self._save_registry(registry)
        self.log.info(f"[PromptManager] 已注册提示词: {prompt.id} -> {relative_path}")

    # ================================================================== #
    #   私有工具方法
    # ================================================================== #
    def _ensure_dirs(self):
        """确保所有必要目录存在"""
        for d in [self.prompts_dir, self.history_dir, self.custom_dir]:
            os.makedirs(d, exist_ok=True)

        # 确保 custom 目录有 .gitkeep
        gitkeep = self.custom_dir / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.touch()

    def _load_registry(self) -> dict:
        """加载 registry.json"""
        if not self.registry_file.exists():
            return {"prompts": {}}
        try:
            with open(self.registry_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.log.error(f"[PromptManager] 加载 registry 失败: {e}")
            return {"prompts": {}}

    def _save_registry(self, data: dict):
        """保存 registry.json"""
        with open(self.registry_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _load_from_file(file_path: Path) -> Prompt:
        """从 JSON 文件加载 Prompt"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return Prompt.from_dict(data)

    @staticmethod
    def _save_to_file(prompt: Prompt, file_path: Path):
        """将 Prompt 写入 JSON 文件"""
        # 导出时去除内部元数据
        export_data = prompt.to_dict()
        export_data.pop("_is_custom", None)
        export_data.pop("_custom_mtime", None)

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

    def _resolve_target_file(self, prompt: Prompt) -> Path:
        """
        确定写入目标文件路径

        如果当前是自定义版本, 写入 custom/;
        否则写入 registry 中记录的原始路径。
        """
        if prompt.metadata.get("_is_custom"):
            return self.custom_dir / f"{prompt.id}.json"

        registry = self._load_registry()
        entry = registry.get("prompts", {}).get(prompt.id, {})
        if entry.get("file"):
            return self.prompts_dir / entry["file"]

        # 最终兜底
        return self.prompts_dir / prompt.platform / f"{prompt.id}.json"
