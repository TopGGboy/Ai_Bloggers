import os
from typing import Dict, Any, Optional
from playwright.async_api import BrowserContext
from app.Bloggers.BasePublisher import BasePublisher
from app.Bloggers.WeiboBlogger.enums import WeiboPublishType


class WeiboPublisher(BasePublisher):
    """微博内容发布器 - 专注于内容生成和发布"""

    def __init__(self, context: BrowserContext, publish_type: WeiboPublishType = WeiboPublishType.ESSAY):
        """
        初始化发布器

        Args:
            context: Playwright BrowserContext 实例
            publish_type: 发布类型，默认为 ESSAY
        """
        super().__init__(platform_name="weibo", context=context)
        self.publish_type = publish_type

    async def publish(self, data: Dict[str, Any]) -> bool:
        """
        发布接口

        Args:
            data: 发布数据字典，包含标题和内容
                - essay模式： {'title': str, 'content': str, 'image_path': str, 'summary': str = None}

        Returns:
            bool: 发布是否成功
        """
        try:
            send_action = self._get_send_action_class()

            if self.publish_type == WeiboPublishType.ESSAY:
                publish_data = {
                    "title": data["title"],
                    "content": data["content"],
                    "image_path": data.get("image_path", None),
                    "summary": data.get("summary", None)
                }
            else:
                self.log.error(f"❌ 不支持的发布类型：{self.publish_type}")
                return False

            return await self.publish_essay(publish_data, send_action)

        except Exception as e:
            self.log.error(f"❌ 发布失败：{e}", exc_info=True)
            return False

    def _get_send_action_class(self):
        """根据发布类型获取对应的发布操作类"""

        if self.publish_type == WeiboPublishType.ESSAY:
            from app.Bloggers.WeiboBlogger.actions.SendEssay import AsyncWeiboSendEssay
            return AsyncWeiboSendEssay(self.page)
        else:
            raise ValueError(f"不支持的发布类型：{self.publish_type}")
