"""
AI生图类
"""
from typing import Optional, Dict

from app.tools.LoggingConfig import LoggingConfig
from app.core.config_manager import config

from app.core.AiAgent.ImageProviders.BaseProvider import BaseProvider
from app.core.AiAgent.ImageProviders.QwenProvider import QwenProvider


class AiImage:
    """
    AI 图片生成管理器
    支持多种图片生成模型的统一调用接口
    """
    # 支持的提供商映射
    PROVIDERS = {
        'qwen': QwenProvider,
        # 'openai': OpenAIProvider,  # 未来扩展
    }

    def __init__(self, provider: str, model_name: str, api_key: str = None):
        """
        初始化AI图片生成管理器
        :param provider: 图片生成模型提供方
        :param model_name: 图片生成模型名称
        :param api_key: 图片生成模型API密钥
        """
        self.log = LoggingConfig(
            log_file_path=config.logfile_path,
            log_level=config.log_level
        ).get_logger(self.__class__.__name__)

        self.current_provider = provider
        self.model_name = model_name
        self.api_key = api_key

        # 创建提供商实例（传递配置）
        self.provider_instance = self._create_provider(provider, model_name, api_key)

    def _create_provider(self, provider_name: str, model_name: str = None, api_key: str = None) -> BaseProvider:
        """
        创建指定的提供商实例

        Args:
            provider_name: 提供商名称
            model_name: 模型名称
            api_key: API密钥
        """
        if provider_name not in self.PROVIDERS:
            raise ValueError(f"不支持的图片生成提供商: {provider_name}。支持的提供商: {list(self.PROVIDERS.keys())}")

        provider_class = self.PROVIDERS[provider_name]

        # 创建实例时传递配置参数
        try:
            provider_instance = provider_class(model_name=model_name, api_key=api_key)
            self.log.info(f"初始化图片生成提供商: {provider_name}, 模型: {model_name}")
            return provider_instance
        except Exception as e:
            self.log.error(f"创建提供商实例失败: {e}")
            raise

    def switch_provider(self, provider_name: str, model_name: str = None, api_key: str = None):
        """
        切换到另一个提供商

        Args:
            provider_name: 新的提供商名称
            model_name: 模型名称（可选）
            api_key: API密钥（可选）
        """
        if provider_name != self.current_provider:
            # 如果未指定模型名称，从配置读取
            if model_name is None:
                model_name = self._get_model_name_from_config(provider_name)

            self.provider_instance = self._create_provider(provider_name, model_name, api_key)
            self.current_provider = provider_name
            self.model_name = model_name
            self.log.info(f"已切换到提供商: {provider_name}, 模型: {model_name}")

    def generate_image(
            self,
            prompt: str,
            size: str = "1024x1024",
            provider: str = None,
            model_name: str = None,
            api_key: str = None,
            negative_prompt: str = "",
            **kwargs
    ) -> dict:
        """
        生成图片（同步）

        Args:
            prompt: 图片描述提示词
            size: 图片尺寸，如 "1024x1024", "1792x1024"
            provider: 临时指定提供商，不指定则使用当前提供商
            model_name: 临时指定模型名称
            api_key: 临时指定 API Key
            negative_prompt: 负面提示词
            **kwargs: 传递给提供商的其他参数

        Returns:
            dict: 包含生成结果的字典
        """
        # 如果指定了临时提供商，切换到该提供商
        if provider and provider != self.current_provider:
            original_provider = self.current_provider
            original_model = self.model_name
            self.switch_provider(provider, model_name, api_key)
            result = self.provider_instance.generate_image(prompt, size, **kwargs)
            # 恢复原提供商
            self.switch_provider(original_provider, original_model)
            return result

        return self.provider_instance.generate_image(prompt=prompt, size=size, negative_prompt=negative_prompt, **kwargs)

    async def generate_image_async(
            self,
            prompt: str,
            size: str = "1024x1024",
            provider: str = None,
            model_name: str = None,
            api_key: str = None,
            **kwargs
    ) -> dict:
        """
        生成图片（异步）

        Args:
            prompt: 图片描述提示词
            size: 图片尺寸
            provider: 临时指定提供商
            model_name: 临时指定模型名称
            api_key: 临时指定 API Key
            negative_prompt: 负面提示词
            **kwargs: 传递给提供商的其他参数

        Returns:
            dict: 包含生成结果的字典
        """
        # 提示词格式化
        prompt = self._format_prompt(prompt)

        if provider and provider != self.current_provider:
            original_provider = self.current_provider
            original_model = self.model_name
            self.switch_provider(provider, model_name, api_key)
            result = await self.provider_instance.generate_image_async(prompt, size, **kwargs)
            # 恢复原提供商
            self.switch_provider(original_provider, original_model)
            return result

        return await self.provider_instance.generate_image_async(prompt, size, **kwargs)

    def get_available_providers(self) -> list:
        """获取可用的提供商列表"""
        return list(self.PROVIDERS.keys())


if __name__ == '__main__':
    # 手动指定配置
    ai_image = AiImage(
        provider="qwen",
        model_name="qwen-image-2.0",  # 正确的模型名
        api_key=""
    )

    # 生成图片
    result = ai_image.generate_image(
        prompt="科技城市，未来主义风格，霓虹灯光，夜晚，高楼大厦",
        n=1,
        negative_prompt="低质量，模糊，低分辨率",
        watermark=False  # 不加水印
    )

    print(result)

    if result['success']:
        print(f"\n✅ 图片生成成功！")
        print(f"图片URL: {result['image_url']}")
    else:
        print(f"\n❌ 图片生成失败: {result['error']}")
