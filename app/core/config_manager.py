# app/core/config_manager.py
import yaml
import os
from pathlib import Path
from typing import Any, Dict


class ConfigManager:
    def __init__(self, config_file: str = None):
        if config_file is None:
            self.config_file = Path(__file__).parent.parent / "config/Ai_Blogger.yaml"
        else:
            self.config_file = Path(config_file)

        self._config = self.load_config()

    def load_config(self) -> Dict[str, Any]:
        """加载 YAML 配置文件"""
        if not self.config_file.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.config_file}")

        with open(self.config_file, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)

        # 环境变量覆盖
        self._apply_env_overrides(config_data)
        return config_data

    def _apply_env_overrides(self, config: Dict[str, Any]):
        """应用环境变量覆盖"""

        # 递归处理嵌套字典
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

    def get_deepseek_config(self) -> Dict[str, Any]:
        """获取 DeepSeek API 配置"""
        return self._config['api']['deepseek']

    @property
    def deepseek_api_key(self) -> str:
        """获取 DeepSeek API 密钥"""
        return self._config['api']['deepseek']['api_key']

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
