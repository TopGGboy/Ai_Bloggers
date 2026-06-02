import json
import os
from typing import Optional, List, Tuple
from dashscope import MultiModalConversation
import dashscope
from .base_provider import BaseProvider


class QwenProvider(BaseProvider):
    """通义千问图片生成器（基于 qwen-image-2.0 多模态模型）"""

    # 模型支持的分辨率配置
    MODEL_RESOLUTION_CONFIG = {
        # qwen-image-2.0 和 2.0-pro: 像素范围 512*512 ~ 2048*2048
        "qwen-image-2.0": {
            "type": "range",
            "min_pixels": 512 * 512,  # 262144
            "max_pixels": 2048 * 2048,  # 4194304
            "recommended_sizes": [
                "512x512", "768x768", "1024x1024",
                "1280x720", "720x1280", "1024x768", "768x1024"
            ],
            "multi_image_support": True
        },
        "qwen-image-2.0-pro": {
            "type": "range",
            "min_pixels": 512 * 512,
            "max_pixels": 2048 * 2048,
            "recommended_sizes": [
                "512x512", "768x768", "1024x1024",
                "1280x720", "720x1280", "1024x768", "768x1024"
            ],
            "multi_image_support": True
        },
        # qwen-image-max 和 plus: 固定分辨率
        "qwen-image-max": {
            "type": "fixed",
            "available_sizes": {
                "16:9": "1664x928",
                "4:3": "1472x1104",
                "1:1": "1328x1328",
                "3:4": "1104x1472",
                "9:16": "928x1664"
            },
            "default_size": "1664x928",
            "multi_image_support": False
        },
        "qwen-image-plus-2026-01-09": {
            "type": "fixed",
            "available_sizes": {
                "16:9": "1664x928",
                "4:3": "1472x1104",
                "1:1": "1328x1328",
                "3:4": "1104x1472",
                "9:16": "928x1664"
            },
            "default_size": "1664x928",
            "multi_image_support": False
        }
    }

    def __init__(self, model_name: str = None, api_key: str = None):
        """
        初始化通义千问图片生成器

        Args:
            model_name: 模型名称，默认 qwen-image-2.0
            api_key: API密钥，默认从配置读取
        """
        # 如果未指定模型名称，使用默认值
        if model_name is None:
            model_name = "qwen-image-2.0"

        # 验证模型名称
        if model_name not in self.MODEL_RESOLUTION_CONFIG:
            raise ValueError(
                f"不支持的模型: {model_name}。\n"
                f"支持的模型: {list(self.MODEL_RESOLUTION_CONFIG.keys())}"
            )

        # 调用父类构造函数，传递配置
        super().__init__(
            provider_name="qwen",
            model_name=model_name,
            api_key=api_key
        )

        # 验证配置
        if not self.validate_config():
            raise ValueError(f"通义千问图片生成器配置不完整")

        # 设置 DashScope API
        dashscope.base_http_api_url = 'https://dashscope.aliyuncs.com/api/v1'

        # 获取当前模型的配置
        self.resolution_config = self.MODEL_RESOLUTION_CONFIG[model_name]

        self.log.info(f"初始化通义千问图片生成器，模型: {self.model_name}")
        self.log.info(f"分辨率配置: {self.resolution_config['type']}")

    def _validate_and_adjust_size(self, size: str) -> str:
        """
        验证并调整尺寸以适应当前模型

        Args:
            size: 用户指定的尺寸，如 "1024x1024"

        Returns:
            str: 调整后的有效尺寸
        """
        config_type = self.resolution_config['type']

        if config_type == "range":
            # 范围类型：验证像素数是否在范围内
            try:
                width, height = map(int, size.split('x'))
                pixels = width * height
                min_pixels = self.resolution_config['min_pixels']
                max_pixels = self.resolution_config['max_pixels']

                if pixels < min_pixels:
                    self.log.warning(
                        f"尺寸 {size} 像素数({pixels})小于最小值({min_pixels})，"
                        f"调整为推荐尺寸 1024x1024"
                    )
                    return "1024x1024"
                elif pixels > max_pixels:
                    self.log.warning(
                        f"尺寸 {size} 像素数({pixels})大于最大值({max_pixels})，"
                        f"调整为推荐尺寸 1024x1024"
                    )
                    return "1024x1024"
                else:
                    return size
            except Exception as e:
                self.log.warning(f"尺寸解析失败: {e}，使用默认尺寸 1024x1024")
                return "1024x1024"

        elif config_type == "fixed":
            # 固定类型：匹配最接近的预设尺寸
            available_sizes = self.resolution_config['available_sizes']
            default_size = self.resolution_config['default_size']

            # 直接匹配
            if size in available_sizes.values():
                return size

            # 尝试通过比例匹配
            try:
                width, height = map(int, size.split('x'))
                ratio = width / height

                # 找到最接近的比例
                best_match = None
                min_diff = float('inf')

                for ratio_name, preset_size in available_sizes.items():
                    preset_w, preset_h = map(int, preset_size.split('x'))
                    preset_ratio = preset_w / preset_h
                    diff = abs(ratio - preset_ratio)

                    if diff < min_diff:
                        min_diff = diff
                        best_match = preset_size

                if best_match:
                    self.log.info(
                        f"尺寸 {size} 自动匹配到最接近的预设尺寸: {best_match}"
                    )
                    return best_match
            except Exception as e:
                self.log.warning(f"尺寸匹配失败: {e}，使用默认尺寸 {default_size}")

            # 返回默认尺寸
            self.log.warning(f"无法匹配尺寸 {size}，使用默认尺寸 {default_size}")
            return default_size

        return size

    def generate_image(
            self,
            prompt: str,
            size: str = "1024x1024",
            reference_images: list = None,
            negative_prompt: str = "",
            n: int = 1,
            watermark: bool = True,
            **kwargs
    ) -> dict:
        """
        使用通义千问 qwen-image-2.0 生成图片

        Args:
            prompt: 图片描述提示词
            size: 图片尺寸，会根据模型自动调整
            reference_images: 参考图片 URL 列表（可选）
            negative_prompt: 负面提示词
            n: 生成图片数量
            watermark: 是否添加水印
            **kwargs: 其他参数

        Returns:
            dict: 生成结果
        """
        if not self.validate_prompt(prompt):
            return {
                'success': False,
                'image_url': None,
                'image_path': None,
                'error': '提示词无效'
            }

        # 检查多图支持
        if reference_images and not self.resolution_config.get('multi_image_support', True):
            self.log.warning(f"模型 {self.model_name} 不支持多图输入，忽略参考图片")
            reference_images = None

        # 验证并调整尺寸
        adjusted_size = self._validate_and_adjust_size(size)
        if adjusted_size != size:
            self.log.info(f"尺寸已从 {size} 调整为 {adjusted_size}")

        try:
            self.log.info(
                f"使用通义千问生成图片，模型: {self.model_name}, "
                f"尺寸: {adjusted_size}, 提示词: {prompt[:50]}..."
            )

            # 构建消息内容
            content = []

            # 如果有参考图片，先添加图片
            if reference_images:
                for img_url in reference_images:
                    content.append({"image": img_url})

            # 添加文本提示词
            content.append({"text": prompt})

            # 构建消息
            messages = [
                {
                    "role": "user",
                    "content": content
                }
            ]

            self.log.debug(f"调用 API，参数: n={n}, watermark={watermark}")

            # 调用多模态对话 API
            response = MultiModalConversation.call(
                api_key=self.api_key,
                model=self.model_name,
                messages=messages,
                result_format='message',
                stream=False,
                n=n,
                watermark=watermark,
                negative_prompt=negative_prompt
            )

            # 解析响应
            if response.status_code == 200:
                output = response.output
                choices = output.get('choices', [])

                if choices:
                    first_choice = choices[0]
                    message = first_choice.get('message', {})
                    content_list = message.get('content', [])

                    image_urls = []
                    for item in content_list:
                        if 'image' in item:
                            image_urls.append(item['image'])

                    if image_urls:
                        self.log.info(f"图片生成成功，共 {len(image_urls)} 张")
                        return {
                            'success': True,
                            'image_url': image_urls[0],
                            'image_urls': image_urls,
                            'image_path': None,
                            'error': None,
                            'size': adjusted_size
                        }
                    else:
                        error_msg = "生成结果中没有找到图片 URL"
                        self.log.error(f"{error_msg}, 响应: {response}")
                        return {
                            'success': False,
                            'image_url': None,
                            'image_path': None,
                            'error': error_msg
                        }
                else:
                    error_msg = "生成结果为空"
                    self.log.error(error_msg)
                    return {
                        'success': False,
                        'image_url': None,
                        'image_path': None,
                        'error': error_msg
                    }
            else:
                error_msg = f"API 调用失败: {response.code} - {response.message}"
                self.log.error(error_msg)
                return {
                    'success': False,
                    'image_url': None,
                    'image_path': None,
                    'error': error_msg
                }

        except Exception as e:
            self.log.error(f"通义千问图片生成失败: {e}")
            return {
                'success': False,
                'image_url': None,
                'image_path': None,
                'error': str(e)
            }

    async def generate_image_async(
            self,
            prompt: str,
            size: str = "1024x1024",
            negative_prompt: str = "",
            **kwargs
    ) -> dict:
        """异步生成图片"""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.generate_image(prompt=prompt, size=size, negative_prompt=negative_prompt, **kwargs)
        )

    def get_supported_sizes(self) -> dict:
        """
        获取当前模型支持的尺寸信息

        Returns:
            dict: 支持的尺寸配置
        """
        return {
            'model': self.model_name,
            'config_type': self.resolution_config['type'],
            'multi_image_support': self.resolution_config.get('multi_image_support', True),
            'sizes': self.resolution_config.get(
                'recommended_sizes' if self.resolution_config['type'] == 'range'
                else 'available_sizes'
            )
        }
