import os
import tempfile
from typing import Dict, Any, Optional
from playwright.async_api import BrowserContext
from app.Bloggers.BasePublisher import BasePublisher
from app.Bloggers.ZhihuBlogger.enums import ZhihuPublishType


class ZhihuPublisher(BasePublisher):
    """知乎内容发布器 - 只负责发布，通过传入不同的 Action 类来区分类型"""

    def __init__(self, context: BrowserContext, publish_type: ZhihuPublishType = ZhihuPublishType.ANSWER):
        """
        初始化发布器

        Args:
            context: Playwright BrowserContext 实例
            publish_type: 发布类型（回答/文章）
        """
        super().__init__(platform_name="zhihu", context=context)
        self.publish_type = publish_type

    async def publish(self, data: Dict[str, Any]) -> bool:
        """
        统一发布接口 - 根据发布类型自动选择对应的 Action

        Args:
            data: 发布数据字典
                - 回答模式: {'href': str, 'docx_path': str}
                - 文章模式: {'title': str, 'md_path': str, 'image_path': str (可选)}

        Returns:
            bool: 发布是否成功
        """
        global temp_docx_path
        try:
            send_action = self._get_send_action_class()
            # 回答模式需要将 Markdown 转换为 DOCX（临时文件）
            json_data = data.get('json_data')

            # 创建临时 DOCX 文件
            temp_file = tempfile.NamedTemporaryFile(suffix='.docx', delete=False, dir=self.temp_path)
            temp_docx_path = temp_file.name
            temp_file.close()

            # 转换 Markdown 为 DOCX
            from app.tools.Md2Docx import MarkdownToDocx
            converter = MarkdownToDocx()
            converter.md_text_to_docx(json_data['content'], temp_docx_path)

            self.log.info(f"✅ Markdown 已转换为临时 DOCX: {temp_docx_path}")

            if self.publish_type == ZhihuPublishType.ANSWER:

                # 回答模式需要转换数据格式
                publish_data = {
                    'href': data.get('href'),
                    'docx_path': temp_docx_path
                }
            elif self.publish_type == ZhihuPublishType.ARTICLE:
                # 文章模式直接使用
                publish_data = {
                    'title': data.get('title'),
                    'docx_path': temp_docx_path,
                    'image_path': data.get('image_path', None)
                }
            else:
                self.log.error(f"❌ 不支持的发布类型：{self.publish_type}")
                return False

            return await self.publish_essay(publish_data, send_action)

        except Exception as e:
            self.log.error(f"❌ 发布失败：{e}", exc_info=True)
            return False

        finally:
            # 清理临时文件
            if temp_docx_path and os.path.exists(temp_docx_path):
                try:
                    os.remove(temp_docx_path)
                    self.log.info(f"🗑️ 临时文件已删除: {temp_docx_path}")
                except Exception as e:
                    self.log.warning(f"⚠️ 删除临时文件失败: {e}")

    def _get_send_action_class(self):
        """
        根据发布类型获取对应的 Send Action 类

        Returns:
            SendAction 类的实例
        """
        if self.publish_type == ZhihuPublishType.ANSWER:
            from app.Bloggers.ZhihuBlogger.actions.SendAnswer import AsyncZhihuSendAnswer
            return AsyncZhihuSendAnswer(page=self.page)
        elif self.publish_type == ZhihuPublishType.ARTICLE:
            from app.Bloggers.ZhihuBlogger.actions.SendArticle import AsyncZhihuSendArticle
            return AsyncZhihuSendArticle(page=self.page)
        else:
            raise ValueError(f"不支持的发布类型：{self.publish_type}")
