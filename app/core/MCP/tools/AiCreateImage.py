"""
AI图片创建工具
"""
from app.core.AiAgent.ImageProviders.QwenProvider import QwenProvider


class AiCreateImage:
    """
    AI图片创建工具
    """

    def __init__(self, provider: str, model_name: str = None, api_key: str = None):
        self.provider = provider
        self.model_name = model_name
        self.api_key = api_key

        self.image_provider = QwenProvider(self.model_name, self.api_key)

    async def create_image_async(self, prompt: str, size: str = "1664x928", negative_prompt: str = ""):
        """
        创建图片异步版本(单图)

        Args:
            prompt: 图片描述
            size: 图片尺寸
            negative_prompt: 负面提示词
        Returns:
            dict: 包含生成结果的字典
        """
        try:
            result = await self.image_provider.generate_image_async(prompt=prompt, size=size,
                                                                    negative_prompt=negative_prompt)

            if not result["success"]:
                return {"success": False, "message": "图片生成失败", "image_url": ""}

            return {"success": True, "message": "图片生成成功", "image_url": result["image_url"]}
        except Exception as e:
            return {"success": False, "message": f"图片生成失败: {e}", "image_url": ""}

    def create_image(self, prompt: str, size: str = "1664x928", negative_prompt: str = ""):
        """
        创建图片同步版本(单图)

        Args:
            prompt: 图片描述
        Returns:

        """
        try:
            result = self.image_provider.generate_image(prompt=prompt, size=size, negative_prompt=negative_prompt)

            if not result["success"]:
                return {"success": False, "message": "图片生成失败", "image_url": ""}

            return {"success": True, "message": "图片生成成功", "image_url": result["image_url"]}
        except Exception as e:
            return {"success": False, "message": f"图片生成失败: {e}", "image_url": ""}

    def get_function(self):
        """返回给 ToolRegistry 注册的异步函数"""
        return self.create_image_async
