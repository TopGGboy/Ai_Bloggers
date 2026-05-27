# app/core/config_manager.py
import os
import re
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class ConfigManager:
    """
    全局配置管理器

    加载优先级（高→低）：
      1. 系统环境变量 (os.environ)
      2. .env 文件（项目根目录）
      3. Ai_Blogger.yaml 配置文件
    """

    # --- 敏感字段映射表：YAML路径 → 环境变量名 ---
    # 格式: ("yaml.dotted.path", "ENV_VAR_NAME", 默认值)
    SENSITIVE_FIELDS = [
        ("api.deepseek.api_key", "DEEPSEEK_API_KEY", ""),
        ("platforms.zhihu.user_name", "ZHIHU_USERNAME", ""),
        ("platforms.zhihu.password", "ZHIHU_PASSWORD", ""),
        ("platforms.weibo.user_name", "WEIBU_USERNAME", ""),
        ("platforms.weibo.password", "WEIBU_PASSWORD", ""),
        ("platforms.zhihu.tools.create_image.api_key", "QWEN_API_KEY", ""),
    ]

    def __init__(self, config_file: str = None, env_file: str = None):
        if config_file is None:
            self.config_file = Path(__file__).parent.parent / "config/Ai_Blogger.yaml"
        else:
            self.config_file = Path(config_file)

        # 定位 .env 文件：显式指定 → 项目根目录
        if env_file is None:
            self.env_file = Path(__file__).parent.parent.parent / ".env"
        else:
            self.env_file = Path(env_file)

        self._config = self.load_config()

    def load_config(self) -> Dict[str, Any]:
        """加载配置：加载 .env → 读 YAML 原文 → 替换 ${} 占位符 → 解析 → 兜底覆盖"""
        # 步骤1：加载 .env 到 os.environ（不覆盖已有系统环境变量）
        self._load_env_file()

        # 步骤2：读取 YAML 原始文本
        if not self.config_file.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.config_file}")

        with open(self.config_file, 'r', encoding='utf-8') as f:
            raw_yaml_text = f.read()

        # 步骤3：在纯文本上替换 ${VAR} 和 ${VAR:-default} 占位符
        processed_text = self._resolve_env_placeholders(raw_yaml_text)

        # 步骤4：将替换后的文本解析为字典
        config_data = self._load_yaml_safely(processed_text)
        if config_data is None:
            raise ValueError(f"YAML 配置文件解析失败或内容为空: {self.config_file}")

        # 步骤5：用环境变量兜底覆盖敏感字段（双重保障）
        self._apply_sensitive_overrides(config_data)

        return config_data

    @staticmethod
    def _load_yaml_safely(yaml_text: str) -> Optional[Dict[str, Any]]:
        """安全地解析 YAML 文本，返回字典；解析失败时返回 None 并记录日志"""
        try:
            import yaml
            result = yaml.safe_load(yaml_text)
            if result is None:
                logger.warning("YAML 配置文件内容为空")
            return result if isinstance(result, dict) else {}
        except ImportError:
            logger.error("未安装 PyYAML 库，请执行: pip install pyyaml")
            raise
        except Exception as e:
            logger.error(f"YAML 解析错误: {e}")
            raise

    def _load_env_file(self):
        """加载 .env 文件到 os.environ"""
        if not self.env_file.exists():
            logger.info(f".env 文件不存在，跳过加载: {self.env_file}")
            return

        try:
            # python-dotenv：不会覆盖已有的系统环境变量
            load_dotenv(self.env_file, override=False)
            logger.debug(f"已从 .env 加载环境变量: {self.env_file}")
        except Exception as e:
            logger.warning(f"加载 .env 文件失败（可忽略）: {e}")

    @staticmethod
    def _resolve_env_placeholders(yaml_text: str) -> str:
        """
        替换 YAML 纯文本中的环境变量占位符，支持两种语法：
          ${VAR_NAME}           — 必填，缺失则保留原样便于排错
          ${VAR_NAME:-default}  — 可选，缺失时使用 default

        符合 12-factor App 的配置外置原则。
        """
        pattern = re.compile(
            r'\$\{(\w+)(?::-([^}]*))?\}'
        )

        def replacer(match):
            var_name = match.group(1)
            default_val = match.group(2)  # 可能为 None
            env_val = os.getenv(var_name)
            if env_val is not None:
                return env_val
            if default_val is not None:
                return default_val
            # 环境变量缺失且无默认值：保留原文本便于排错
            return match.group(0)

        return pattern.sub(replacer, yaml_text)

    def _apply_sensitive_overrides(self, config: Dict[str, Any]):
        """
        通过预定义的映射表，将环境变量值回写到 config 字典中。
        这是双重保障：即使 YAML 未使用 ${} 语法，
        只要 .env / 系统环境中存在对应变量，也能正确注入。
        """
        for yaml_path, env_key, _ in self.SENSITIVE_FIELDS:
            env_value = os.getenv(env_key)
            if env_value is None:
                continue

            keys = yaml_path.split('.')
            target = config
            for key in keys[:-1]:
                if key in target and isinstance(target[key], dict):
                    target = target[key]
                else:
                    break
            else:
                final_key = keys[-1]
                if isinstance(target, dict) and final_key in target:
                    target[final_key] = env_value
                    logger.debug(f"敏感字段已通过环境变量覆盖: {yaml_path}")

    def _apply_env_overrides(self, config: Dict[str, Any]):
        """应用环境变量覆盖（通用递归方式，保留原有兼容性）"""

        def update_from_env(data, prefix=""):
            for key, value in data.items():
                env_key = f"{prefix}{key}".upper().replace('.', '_')
                env_value = os.getenv(env_key)

                if env_value is not None:
                    if isinstance(value, int):
                        data[key] = int(env_value)
                    elif isinstance(value, bool):
                        data[key] = env_value.lower() in ('true', '1', 'yes')
                    elif isinstance(value, float):
                        data[key] = float(env_value)
                    else:
                        data[key] = env_value

                if isinstance(value, dict):
                    update_from_env(value, f"{env_key}_")

        update_from_env(config)

    @property
    def logfile_path(self) -> Path:
        return Path(self._config['app']['logfile_path'])

    @property
    def log_level(self) -> str:
        return self._config['app']['log_level']

    @property
    def debug_mode(self) -> bool:
        return self._config['app']['debug_mode']

    @property
    def temp_path(self) -> Path:
        return Path(self._config['app']['temp_path'])

    def get_deepseek_config(self) -> Dict[str, Any]:
        """获取 DeepSeek API 配置"""
        return self._config['api']['deepseek']

    @property
    def deepseek_api_key(self) -> str:
        """获取 DeepSeek API 密钥"""
        return self._config['api']['deepseek']['api_key']

    @property
    def platforms(self) -> str:
        """获取平台配置"""
        return self._config['platforms']

    @property
    def competition_platform(self) -> str:
        """获取竞品平台配置"""
        return self._config['content_pipeline']['competition_platform']

    def get(self, path: str, default=None):
        """获取嵌套配置值，支持路径访问如 'app.log_level'"""
        keys = path.split('.')
        value = self._config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value


# 全局配置实例
config = ConfigManager()
