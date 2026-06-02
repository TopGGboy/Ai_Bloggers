"""
知乎创作者数据采集器（异步版）

从知乎创作者中心获取回答/文章的阅读量、点赞数等数据。
Cookie 通过 CookieManager 从 Playwright storage_state 动态加载，不再硬编码。
"""
from typing import Dict, Optional, Union, Any
from pathlib import Path
from datetime import datetime
import aiohttp

from app.request_spiders.cookie_manager import CookieManager

# 通用请求头（不含 Cookie，仅含静态字段）
BASE_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-language": "zh-CN,zh;q=0.9,en-US;q=0.8,en-GB;q=0.7,en;q=0.6",
    "cache-control": "max-age=0",
    "priority": "u=0, i",
    "referer": "https://www.zhihu.com/creator/manage/creation/all",
    "sec-ch-ua": '"Chromium";v="148", "Microsoft Edge";v="148", "Not/A)Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
}

# 知乎创作者中心接口所需的精确 cookie 字段列表
NEEDED_ZHIHU_COOKIES = [
    "SESSIONID",
    "Hm_lvt_98beee57fd2ef70ccdd5ca52b9740c49",
    "edu_user_uuid",
    "_zap",
    "d_c0",
    "_xsrf",
    "__snaker__id",
    "q_c1",
    "gdxidpyhxdE",
    "captcha_session_v2",
    "z_c0",
    "__zse_ck",
    "SUBMIT_0",
    "BEC",
]


class AsyncZhihuMetricsCollector:
    """知乎创作者数据采集器（异步版）"""

    def __init__(self, storage_state_path: Optional[Union[str, Path]] = None):
        """
        初始化采集器

        :param storage_state_path: 可选，Playwright storage_state.json 路径
                                   若不指定则自动通过 CookieManager(platform='zhihu') 解析
        """
        self.cookie_manager = CookieManager(
            storage_state_path=storage_state_path,
            platform='zhihu' if storage_state_path is None else None
        )
        # 请求超时时间
        self.timeout = 15

    @staticmethod
    def _clean_number(val: Any) -> int:
        """
        清洗数值字段: null/None -> 0, bool -> 0（防止 isinstance(False, int) 陷阱）
        """
        if val is None or isinstance(val, bool):
            return 0
        return int(val) if isinstance(val, (int, float)) else 0

    @staticmethod
    def _clean_percent(val: Any) -> Optional[float]:
        """
        清洗百分比字符串/数值:
          - null/None -> None（保留"无数据"语义）
          - "NaN%"    -> None（无意义值）
          - "0.00%"   -> 0.0
          - 数值 0.0  -> 0.0
        """
        # None/null 显式返回 None，与 "0.00%" 区分
        if val is None:
            return None
        # 如果是数值（如 0.0），直接返回
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            return float(val)
        # 字符串处理
        if isinstance(val, str):
            if val.upper() == "NAN%":
                return None
            try:
                return float(val.replace("%", ""))
            except (ValueError, TypeError):
                return 0.0
        return 0.0

    @staticmethod
    def _timestamp_to_datetime(ts: int) -> Optional[datetime]:
        """
        秒级时间戳转为 datetime 对象
        """
        if not isinstance(ts, int) or ts <= 0:
            return None
        return datetime.fromtimestamp(ts)

    @staticmethod
    def _parse_datetime_string(dt_str: Any) -> Optional[datetime]:
        """
        解析 "YYYY-MM-DD HH:MM:SS" 格式的日期字符串（知乎 API 实际返回格式）

        null/None/False/True → None（非合法日期值）
        """
        if dt_str is None or isinstance(dt_str, bool):
            return None
        try:
            return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return None

    async def fetch_answer_metrics(self, id: Union[str, int], start_date: str = "2026-05-02",
                                   end_date: str = "2026-05-31", type: str = "answer") -> Dict[str, Any]:
        """
        获取指定回答/文章的创作者中心全量指标数据

        :param id: 回答或文章 ID
        :param start_date: 统计开始日期，格式 "YYYY-MM-DD"
        :param end_date: 统计结束日期，格式 "YYYY-MM-DD"
        :param type: 内容类型，"answer" 回答 / "article" 文章
        :return: 清洗、结构化后的全量指标字典
        """
        url = "https://www.zhihu.com/api/v4/creators/analysis/realtime/content/aggr"
        params = {
            "type": type,
            "token": str(id),
            "start": start_date,
            "end": end_date
        }
        raw_data = await self._request(url, params)
        return self._parse_answer_metrics(raw_data)

    def _parse_answer_metrics(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析JSON响应，提取全量指标 + 数据清洗 + 结构化分组
        """
        # ========== 1. 累计总数据（发布至今汇总） ==========
        total_data = {
            "pv": self._clean_number(raw_data.get("pv")),  # 页面浏览量
            "play": self._clean_number(raw_data.get("play")),  # 视频播放量
            "show": self._clean_number(raw_data.get("show")),  # 曝光/展示量
            "upvote": self._clean_number(raw_data.get("upvote")),  # 赞同数
            "like": self._clean_number(raw_data.get("like")),  # 喜欢/爱心点赞
            "comment": self._clean_number(raw_data.get("comment")),  # 评论数
            "collect": self._clean_number(raw_data.get("collect")),  # 收藏数
            "share": self._clean_number(raw_data.get("share")),  # 分享数
            "reaction": self._clean_number(raw_data.get("reaction")),  # 情绪轻互动数
            "re_pin": self._clean_number(raw_data.get("re_pin")),  # 转载 / 二次转发数
            "like_and_reaction": self._clean_number(raw_data.get("like_and_reaction")),  # 喜欢 + 情绪互动合计
            # 环比增减
            "incr_upvote_num": self._clean_number(raw_data.get("incr_upvote_num")),  # 赞同数 环比增量
            "desc_upvote_num": self._clean_number(raw_data.get("desc_upvote_num")),  # 赞同数 环比减量
            "incr_like_num": self._clean_number(raw_data.get("incr_like_num")),  # 喜欢数 环比增量
            "desc_like_num": self._clean_number(raw_data.get("desc_like_num")),  # 喜欢数 环比减量
            # 当期新增
            "new_like": self._clean_number(raw_data.get("new_like")),  # 当期新增喜欢数
            "new_upvote": self._clean_number(raw_data.get("new_upvote")),  # 当期新增赞同数
            "new_incr_upvote_num": self._clean_number(raw_data.get("new_incr_upvote_num")),  # 新增赞同的环比增量
            "new_upvote_7d_num": self._clean_number(raw_data.get("new_upvote_7d_num")),  # 近 7 日新增赞同数
            "new_desc_upvote_num": self._clean_number(raw_data.get("new_desc_upvote_num")),  # 新增赞同的环比减量
            "new_incr_like_num": self._clean_number(raw_data.get("new_incr_like_num")),  # 新增喜欢的环比增量
            "new_desc_like_num": self._clean_number(raw_data.get("new_desc_like_num")),  # 新增喜欢的环比减量
        }

        # ========== 2. 昨日数据 ==========
        yesterday_raw = raw_data.get("yesterday", {})
        yesterday_adv = yesterday_raw.get("advanced", {})
        yesterday_data = {
            "p_date": yesterday_raw.get("p_date", ""),  # 统计日期
            "pv": self._clean_number(yesterday_raw.get("pv")),
            "play": self._clean_number(yesterday_raw.get("play")),
            "show": self._clean_number(yesterday_raw.get("show")),
            "upvote": self._clean_number(yesterday_raw.get("upvote")),
            "like": self._clean_number(yesterday_raw.get("like")),
            "comment": self._clean_number(yesterday_raw.get("comment")),
            "collect": self._clean_number(yesterday_raw.get("collect")),
            "share": self._clean_number(yesterday_raw.get("share")),
            "reaction": self._clean_number(yesterday_raw.get("reaction")),
            "re_pin": self._clean_number(yesterday_raw.get("re_pin")),
            "like_and_reaction": self._clean_number(yesterday_raw.get("like_and_reaction")),
            # 高级指标
            "advanced": {
                "finish_read_percent": self._clean_number(yesterday_adv.get("finish_read_percent", "0.00%")),  # 完读率
                "positive_interact_percent": self._clean_percent(
                    yesterday_adv.get("positive_interact_percent", "0.00%")),  # 正向互动占比
                "follower_translate": self._clean_number(yesterday_adv.get("follower_translate")),  # 粉丝转化数
                "status": yesterday_adv.get("status", "normal")  # 数据状态
            }
        }

        # ========== 3. 今日实时数据 ==========
        today_raw = raw_data.get("today", {})
        today_adv = today_raw.get("advanced", {})
        today_data = {
            "p_date": today_raw.get("p_date", ""),
            "pv": self._clean_number(today_raw.get("pv")),
            "play": self._clean_number(today_raw.get("play")),
            "show": self._clean_number(today_raw.get("show")),
            "upvote": self._clean_number(today_raw.get("upvote")),
            "like": self._clean_number(today_raw.get("like")),
            "comment": self._clean_number(today_raw.get("comment")),
            "collect": self._clean_number(today_raw.get("collect")),
            "share": self._clean_number(today_raw.get("share")),
            "reaction": self._clean_number(today_raw.get("reaction")),
            "re_pin": self._clean_number(today_raw.get("re_pin")),
            "like_and_reaction": self._clean_number(today_raw.get("like_and_reaction")),
            # 高级指标
            "advanced": {
                "finish_read_percent": self._clean_number(today_adv.get("finish_read_percent", "0.00%")),
                "positive_interact_percent": self._clean_percent(today_adv.get("positive_interact_percent", "0.00%")),
                "follower_translate": self._clean_number(today_adv.get("follower_translate")),
                "status": today_adv.get("status", "normal")
            }
        }

        # ========== 4. 全局高级指标 ==========
        adv_raw = raw_data.get("advanced", {})
        advanced_data = {
            "finish_read_percent": self._clean_number(adv_raw.get("finish_read_percent", "0.00%")),
            "positive_interact_percent": self._clean_percent(adv_raw.get("positive_interact_percent", "0.00%")),
            "follower_translate": self._clean_number(adv_raw.get("follower_translate")),
            "status": adv_raw.get("status", "normal")
        }

        # ========== 5. 作品基础元数据 ==========
        answer_raw = raw_data.get("answer", {})
        answer_meta = {
            "content_id": answer_raw.get("id", ""),
            "url_token": answer_raw.get("url_token", ""),
            "title": answer_raw.get("title", ""),
            "excerpt": answer_raw.get("excerpt", ""),
            "question_id": answer_raw.get("question_id", ""),
            "thumbnail": answer_raw.get("thumbnail", ""),
            "answer_type": answer_raw.get("answer_type", ""),
            "sub_type": answer_raw.get("sub_type", ""),
            "is_video_answer": self._clean_number(answer_raw.get("is_video_answer")),
            "duration": self._clean_number(answer_raw.get("duration")),
            "created_time": self._timestamp_to_datetime(answer_raw.get("created_time")),
            "updated_time": self._timestamp_to_datetime(answer_raw.get("updated_time")),
            "paid_answer": self._clean_percent(answer_raw.get("paid_answer", False)),
            "co_creation": {
                "is_co_creation": self._clean_percent(answer_raw.get("co_creation", False)),
                "own": self._clean_number(answer_raw.get("own", 0))
            }
        }
        # 组装最终结果
        result = {
            "total": total_data,
            "yesterday": yesterday_data,
            "today": today_data,
            "advanced": advanced_data,
            "content_meta": answer_meta
        }
        return result

    def _get_cookies(self) -> Dict[str, str]:
        """精确获取知乎所需的 cookie 字段"""
        return self.cookie_manager.get_cookies_by_names(
            NEEDED_ZHIHU_COOKIES,
            domain_filter='.zhihu.com'
        )

    async def _request(self, url: str, params: Dict[str, str] = None) -> Dict[str, Any]:
        """发送带有动态 Cookie 的异步 GET 请求，返回解析后的 JSON dict"""
        cookies = self._get_cookies()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        url=url,
                        headers=BASE_HEADERS,
                        cookies=cookies,
                        params=params,
                        timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as resp:
                    # 状态码校验：401/403 代表 Cookie 失效
                    if resp.status in (401, 403):
                        raise PermissionError("Cookie 已失效或权限不足，请重新登录刷新 Cookie")
                    if resp.status != 200:
                        raise RuntimeError(f"接口异常，状态码: {resp.status}")
                    return await resp.json()
        except aiohttp.ClientError as e:
            raise ConnectionError(f"请求接口失败: {str(e)}")


if __name__ == '__main__':
    import asyncio


    async def main():
        collector = AsyncZhihuMetricsCollector()
        try:
            metrics_result = await collector.fetch_answer_metrics("2016869402193175389")
            import json
            print(json.dumps(metrics_result, indent=2, ensure_ascii=False, default=str))
        except Exception as e:
            print(f"采集失败: {e}")


    asyncio.run(main())
