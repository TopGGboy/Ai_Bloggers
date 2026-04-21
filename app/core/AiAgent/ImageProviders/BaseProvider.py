from abc import ABC, abstractmethod
from typing import Optional
from app.tools.LoggingConfig import LoggingConfig
from app.core.config_manager import config


class BaseProvider(ABC):
    """基础图片提供器类"""

    def __init__(self, provider_name: str, model_name: str = None, api_key: str = None):
        """
        初始化基础图片提供器

        Args:
            provider_name: 提供商名称（如 qwen, openai, deepseek）
            model_name: 模型名称（如 wanx-v1, dall-e-3）
            api_key: API密钥（可选，优先使用传入的，否则从配置读取）
        """
        self.provider_name = provider_name
        self.model_name = model_name
        self.api_key = api_key

        self.log = LoggingConfig(
            log_file_path=config.logfile_path,
            log_level=config.log_level,
        ).get_logger(f"{self.provider_name}")

    @abstractmethod
    def generate_image(
            self,
            prompt: str,
            size: str = "1024x1024",
            **kwargs
    ) -> dict:
        """
       生成图片

       Args:
           prompt: 图片描述提示词
           size: 图片尺寸
           **kwargs: 其他参数

       Returns:
           dict: {
               'success': bool,
               'image_url': str or None,
               'image_path': str or None,
               'error': str or None
           }
        """
        pass

    @abstractmethod
    async def generate_image_async(
            self,
            prompt: str,
            size: str = "1024x1024",
            **kwargs
    ) -> dict:
        """异步生成图片"""
        pass

    def validate_prompt(self, prompt: str) -> bool:
        """验证提示词是否合法"""
        if not prompt or len(prompt.strip()) == 0:
            self.log.error("提示词不能为空")
            return False
        return True

    def validate_config(self) -> bool:
        """验证配置是否完整"""
        if not self.api_key or self.api_key == "<KEY>":
            self.log.error(f"提供商 {self.provider_name} 的 API Key 未配置")
            return False

        if not self.model_name:
            self.log.error(f"提供商 {self.provider_name} 的模型名称未配置")
            return False

        return True
