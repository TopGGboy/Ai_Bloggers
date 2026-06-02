import os
import json
from datetime import datetime
from app.tools.logging_config import LoggingConfig
from app.core.config_manager import config
from app.tools.str_to_md import Str2Md
from app.bloggers.base_writer import BaseWriter


class WeiboWriter(BaseWriter):
    """
    微博博主文章创作器

    当前完全继承 BaseWriter 的实现
    预留此类用于未来可能的微博特定功能扩展
    """

    def __init__(self):
        super().__init__(platform_name="weibo")


