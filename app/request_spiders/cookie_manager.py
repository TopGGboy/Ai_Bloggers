"""
Cookie管理器模块

用于从Playwright的storage_state.json文件中提取、管理和使用cookies
支持按平台名称自动定位文件路径（zhihu / weibo）
"""

import json
from typing import Dict, List, Optional, Union
from pathlib import Path


class CookieManager:
    """从 Playwright storage_state.json 管理 Cookie 的管理器"""

    # 平台名称到 storage_state 子目录的映射（兜底用）
    PLATFORM_DIR_MAP = {
        'zhihu': 'zhihu_data',
        'weibo': 'weibo_data',
    }

    def __init__(self, storage_state_path: Optional[Union[str, Path]] = None,
                 platform: Optional[str] = None):
        """
        初始化Cookie管理器
        支持两种方式指定数据源（二选一）：

        :param storage_state_path: Playwright的storage_state.json文件路径（直接指定）
        :param platform: 平台名称（'zhihu' / 'weibo'），自动从项目配置定位文件路径
        """
        if platform and storage_state_path is None:
            storage_state_path = self._resolve_platform_path(platform)

        if storage_state_path is None:
            raise ValueError("必须指定 storage_state_path 或 platform 参数")

        self.storage_state_path = Path(storage_state_path)
        self.cookies_data = {}
        self.load_cookies()

    @staticmethod
    def _resolve_platform_path(platform: str) -> str:
        """
        根据平台名称从全局配置解析 storage_state 文件路径
        优先从 ConfigManager 获取，失败则基于项目目录结构兜底
        """
        # 优先从配置获取
        try:
            from app.core.config_manager import config
            platform_cfg = config.get(f'platforms.{platform}.paths.storage_state')
            if platform_cfg:
                return platform_cfg
        except Exception:
            pass

        # 兜底：基于 base_driver_path 推断
        try:
            from app.core.config_manager import config
            base_path = config.base_driver_path
        except Exception:
            base_path = Path(__file__).resolve().parent.parent.parent / 'driver' / 'playwright_data'

        sub_dir = CookieManager.PLATFORM_DIR_MAP.get(platform, platform)
        return str(Path(base_path) / sub_dir / 'storage_state.json')

    def load_cookies(self):
        """从Playwright的storage_state.json文件中加载cookies"""
        if not self.storage_state_path.exists():
            raise FileNotFoundError(
                f"Playwright的storage_state.json文件不存在: {self.storage_state_path}"
            )

        with open(self.storage_state_path, 'r', encoding='utf-8') as f:
            storage_state = json.load(f)

        if 'cookies' not in storage_state:
            raise ValueError("storage_state.json文件中没有找到cookies字段")

        self.cookies_data = storage_state

    def get_all_cookies(self) -> List[Dict]:
        """获取所有cookies信息"""
        return self.cookies_data.get('cookies', [])

    def get_cookies_dict(self, domain_filter: Optional[str] = None) -> Dict[str, str]:
        """
        将cookies转换为 name→value 字典格式

        Args:
            domain_filter: 可选域名过滤器（如 '.zhihu.com'），只返回匹配域名的cookies

        Returns:
            以cookie名称为键、cookie值为值的字典
        """
        cookies_list = self.get_all_cookies()
        cookies_dict = {}

        for cookie in cookies_list:
            if domain_filter:
                cookie_domain = cookie.get('domain', '')
                if domain_filter not in cookie_domain:
                    continue
            cookies_dict[cookie['name']] = cookie['value']

        return cookies_dict

    def get_cookie_by_name(self, name: str) -> Optional[str]:
        """根据cookie名称获取单个cookie值"""
        for cookie in self.get_all_cookies():
            if cookie['name'] == name:
                return cookie['value']
        return None

    def get_cookies_by_names(self, names: List[str], domain_filter: Optional[str] = None) -> Dict[str, str]:
        """
        精确匹配并获取指定名称的cookie字段

        只返回 names 列表中存在的cookie，未找到的字段不会出现在结果中。

        Args:
            names: 需要获取的cookie名称列表，如 ['_zap', 'd_c0', 'z_c0']
            domain_filter: 可选域名过滤器，只从匹配的域名中查找

        Returns:
            只包含指定名称的cookie字典
        """
        all_dict = self.get_cookies_dict(domain_filter)
        return {name: all_dict[name] for name in names if name in all_dict}

    def get_zhihu_cookies(self) -> Dict[str, str]:
        """获取专门用于知乎的cookies（过滤 .zhihu.com 域名）"""
        return self.get_cookies_dict(domain_filter='.zhihu.com')

    def get_weibo_cookies(self) -> Dict[str, str]:
        """获取专门用于微博的cookies（过滤 .weibo.com 域名）"""
        return self.get_cookies_dict(domain_filter='.weibo.com')

    def get_platform_cookies(self, platform: str) -> Dict[str, str]:
        """
        根据平台名称获取对应的cookies字典

        Args:
            platform: 平台名称 'zhihu' 或 'weibo'

        Returns:
            该平台的cookies字典
        """
        domain_map = {
            'zhihu': '.zhihu.com',
            'weibo': '.weibo.com',
        }
        domain = domain_map.get(platform)
        if domain:
            return self.get_cookies_dict(domain_filter=domain)
        return self.get_cookies_dict()

    def to_requests_cookiejar(self, domain_filter: Optional[str] = None):
        """
        转换为 requests 库兼容的 CookieJar 对象
        可直接用于 requests.Session.cookies 或 requests.get(..., cookies=jar)

        Args:
            domain_filter: 可选域名过滤器

        Returns:
            requests.cookies.RequestsCookieJar 对象
        """
        import requests
        from requests.cookies import create_cookie

        jar = requests.cookies.RequestsCookieJar()
        for cookie in self.get_all_cookies():
            if domain_filter:
                if domain_filter not in cookie.get('domain', ''):
                    continue
            jar.set_cookie(create_cookie(
                name=cookie['name'],
                value=cookie['value'],
                domain=cookie.get('domain', ''),
                path=cookie.get('path', '/'),
            ))
        return jar

    def __repr__(self) -> str:
        return (
            f"<CookieManager path={self.storage_state_path} "
            f"cookies={len(self.get_all_cookies())}>"
        )
