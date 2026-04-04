import os
import json
from datetime import datetime
from app.tools.LoggingConfig import LoggingConfig
from app.core.config_manager import config
from app.tools.Str2Md import Str2Md
from app.Bloggers.BaseWriter import BaseWriter


class ZhihuWriter(BaseWriter):
    """
    知乎文章写作器

    当前完全继承 BaseWriter 的实现
    预留此类用于未来可能的知乎特定功能扩展
    """

    def __init__(self):
        super().__init__(platform_name="zhihu")
