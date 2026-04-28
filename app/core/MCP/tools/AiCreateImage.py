"""
AI图片创建工具
"""
import os
from datetime import datetime
import aiohttp
from pathlib import Path
from app.core.AiAgent.ImageProviders.QwenProvider import QwenProvider
from app.core.config_manager import config


class AiCreateImage:
    """
    AI图片创建工具
    """

    def __init__(self, provider: str, model_name: str = None, platform_name: str = None, api_key: str = None):
        self.provider = provider
        self.model_name = model_name
        self.platform_name = platform_name
        self.api_key = api_key

        self.image_provider = QwenProvider(self.model_name, self.api_key)
        self.image_path = config.platforms[self.platform_name]["paths"].get("image_path")

        # 确保目录存在
        os.makedirs(self.image_path, exist_ok=True)

    async def _download_image(self, image_url: str, filename: str = None) -> str:
        """
        下载图片到本地

        Args:
            image_url: 图片URL
            filename: 自定义文件名（不含扩展名），为空则自动生成

        Returns:
            本地文件完整路径
        """
        try:
            # 生成文件名
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"ai_image_{timestamp}"

            # 确定文件扩展名（默认为.png）
            file_ext = ".png"
            if image_url.lower().endswith(('.jpg', '.jpeg')):
                file_ext = ".jpg"
            elif image_url.lower().endswith('.webp'):
                file_ext = ".webp"

            # 完整文件路径
            file_path = os.path.join(self.image_path, f"{filename}{file_ext}")

            # 下载图片
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    if response.status == 200:
                        content = await response.read()

                        # 保存到本地
                        with open(file_path, 'wb') as f:
                            f.write(content)

                        return file_path
                    else:
                        raise Exception(f"HTTP {response.status}: {response.reason}")

        except Exception as e:
            raise Exception(f"图片下载失败: {e}")

    async def create_image_async(self, prompt: str, size: str = "1664x928", negative_prompt: str = "",
                                 filename: str = None):
        """
        创建图片异步版本(单图)

        Args:
            prompt: 图片描述
            size: 图片尺寸
            negative_prompt: 负面提示词
            filename: 自定义文件名（不含扩展名），为空则自动生成
        Returns:
            dict: 包含生成结果的字典
        """
        try:
            result = await self.image_provider.generate_image_async(prompt=prompt, size=size,
                                                                    negative_prompt=negative_prompt)

            if not result["success"]:
                return {"success": False, "message": "图片生成失败", "image_path": ""}

            # 2. 下载图片到本地
            image_url = result["image_url"]
            local_path = await self._download_image(image_url, filename)

            return {"success": True, "message": "图片生成成功", "image_path": local_path}
        except Exception as e:
            return {"success": False, "message": f"图片生成失败: {e}", "image_path": ""}

    def create_image(self, prompt: str, size: str = "1664x928", negative_prompt: str = "", filename: str = None):
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

            return {"success": True, "message": "图片生成成功", "image_path": result["image_path"]}
        except Exception as e:
            return {"success": False, "message": f"图片生成失败: {e}", "image_path": ""}

    def get_function(self):
        """返回给 ToolRegistry 注册的异步函数"""
        return self.create_image_async


if __name__ == '__main__':
    import asyncio


    async def main():
        create_image = AiCreateImage(provider="Qwen", model_name="qwen-image-2.0", platform_name="zhihu",
                                     api_key=config.platforms["zhihu"]["tools"]["create_image"]["api_key"])
        result = await create_image.create_image_async("一个在城市中的机器人")
        print(result)


    asyncio.run(main())
