import asyncio
from typing import Dict, List, Any
from app.core.AiAgent.IntertSearch import internet_search_async
from app.core.AiAgent.llm import LLM, extract_json_between_markers
from app.tools.LoggingConfig import LoggingConfig
from app.core.config_manager import config
from app.Bloggers.ZhihuBlogger.scraping.SearchContent import AsyncSearchContent


class InfoEnricher:
    """
    信息增强器 - 再创作前主动收集多维度消息

    策略：
    1. 热点语义分析 -> 拆解位 2-3 个维度搜索
    2. 多角度搜多 -> 事件背景 / 数据事实 / 专业解读 / 用户观点
    3. 竞品内容抓取 → 同话题下高赞回答的论点和结构
    4. 输出结构化的「素材包」给创作 LLM 使用
    """

    def __init__(self, page=None):
        self.competitive_flag = False
        self.page = page  # 竞品内容抓取页面
        self.log = LoggingConfig(log_file_path=config.logfile_path, log_level=config.log_level).get_logger(
            f"{self.__class__.__name__}"
        )
        self.llm = LLM()

        self.competition_platform = config.competition_platform
        if self.competition_platform['zhihu']['enabled']:
            self.zhihu_search_content = AsyncSearchContent(self.page)
            self.competitive_flag = True

    async def enrich(self, hot_title: str, hot_content: list) -> dict:
        """
        信息增强器 - 再创作前主动收集多维度消息


        :param hot_title: 热点标题
        :param hot_content: 热点内容
        :return:
        {
            "topic_analysis": {          # 主题分析
                    "category": "社会民生",
                    "key_entities": ["人脉", "职场", ...],
                    "sentiment": "中性偏批判",
                    "controversy_points": [...]
                },
                "fact_pack": [               # 事实包（来自搜索）
                    {"source": "...", "fact": "..."},
                    ...
                ],
                "competitive_insights": [     # 竞品洞察
                    {
                        "platform": "知乎",
                        "top_answer_summary": "...",
                        "key_arguments": [...],
                        "engagement": {"likes": 5000, "comments": 300}
                    }
                ],
                "data_points": [              # 可引用的数据
                    {"value": "80%", "context": "水分流失占比", "source": "..."}
                ]
        }
        """
        self.log.info(f"开始对热点 '{hot_title}' 进行信息增强")

        # 1. 主题分析
        topic_analysis = await self._analyze_topic(hot_title, hot_content)

        # 2. 多维度信息搜索
        fact_pack = await self._search_facts(hot_title, topic_analysis)

        # 3. 竞品洞察（如果可用）
        competitive_insights = []
        if self.competitive_flag and self.page:
            competitive_insights = await self._gather_competitive_insights(hot_title)

        # 4. 数据点提取
        data_points = await self._extract_data_points(hot_title, fact_pack)

        result = {
            "topic_analysis": topic_analysis,
            "fact_pack": fact_pack,
            "competitive_insights": competitive_insights,
            "data_points": data_points
        }

        self.log.info(f"信息增强完成，返回结构化素材包")
        return result

    async def _analyze_topic(self, hot_title: str, hot_content: list) -> dict:
        """分析热点主题，提取关键实体、情感倾向等"""
        try:
            # 构建提示词进行主题分析
            system_prompt = """
            你是一个专业的内容分析师，请分析以下热点话题的各个维度：
            1. 分类（社会民生、科技、财经、娱乐等）
            2. 关键实体（人物、组织、概念等）
            3. 情感倾向（正面、负面、中性）
            4. 争议点（可能引发讨论的焦点）
            """

            user_prompt = f"""
            热点标题：{hot_title}
            热点内容：{''.join(hot_content[:3]) if hot_content else ''}
            
            请按以下JSON格式返回分析结果：
            {{
                "category": "分类",
                "key_entities": ["实体1", "实体2"],
                "sentiment": "情感倾向",
                "controversy_points": ["争议点1", "争议点2"]
            }}
            """

            client = self.llm.create_async_client("deepseek-flash")
            content, _ = await self.llm.get_response_from_llm_async(
                user_prompt=user_prompt,
                client=client,
                system_prompt=system_prompt,
                temperature=0.3,
                model="deepseek-v4-flash"
            )

            # 尝试解析JSON响应
            try:
                topic_analysis = extract_json_between_markers(content)
                return topic_analysis
            except json.JSONDecodeError:
                self.log.error(f"解析JSON分析失败，返回内容：{content}")
                return {
                    "category": "未分类",
                    "key_entities": [],
                    "sentiment": "中性",
                    "controversy_points": []
                }

        except Exception as e:
            self.log.error(f"主题分析失败: {e}")
            return {
                "category": "未分类",
                "key_entities": [],
                "sentiment": "中性",
                "controversy_points": []
            }

    async def _search_facts(self, hot_title: str, topic_analysis: dict) -> list:
        """基于主题分析结果进行多维度事实搜索"""
        facts = []

        try:
            # 从主题分析中提取关键词用于搜索
            keywords = topic_analysis.get("key_entities", [])
            if not keywords:
                keywords = [hot_title.split()[0]]  # 取标题第一个词作为备选

            # 并行执行多个搜索任务
            search_tasks = []
            for keyword in keywords[:3]:  # 限制搜索数量避免过多请求
                search_query = f"{hot_title} {keyword}"
                task = internet_search_async(search_query)
                search_tasks.append(task)

            # 等待所有搜索完成
            search_results = await asyncio.gather(*search_tasks, return_exceptions=True)

            # 整理搜索结果
            for i, result in enumerate(search_results):
                if isinstance(result, Exception):
                    self.log.error(f"搜索任务 {i} 失败: {result}")
                    continue

                if result and result != "无":
                    for item in result:
                        if isinstance(item, dict):
                            facts.append({
                                "source": item.get("summary", "")[:100] + "..." if len(
                                    item.get("summary", "")) > 100 else item.get("summary", ""),
                                "fact": item.get("content", "")[:500] + "..." if len(
                                    item.get("content", "")) > 500 else item.get("content", "")
                            })

        except Exception as e:
            self.log.error(f"事实搜索失败: {e}")

        return facts

    # TODO: 完善竞品洞察功能，考虑添加更多平台和搜索策略
    async def _gather_competitive_insights(self, hot_title: str) -> list:
        """收集竞品平台上的相关内容洞察"""
        insights = []

        try:
            self.log.info(f"开始收集竞品洞察，热点标题: {hot_title}")

            if self.zhihu_search_content:
                max_content = config.competition_platform['zhihu']['max_content']
                max_comments = config.competition_platform['zhihu']['max_comments']

                if max_content <= 0:
                    self.log.warning("最大处理条数必须大于 0")
                    return []

                # 1. 知乎内容搜索
                zhihu_insights = await self.zhihu_search_content.search(query=hot_title, max_items=max_content,
                                                                        max_comments=max_comments)
                for i, zhihu_result in enumerate(zhihu_insights):
                    platform_insight = await self._extract_platform_insight("知乎", zhihu_result, i + 1)
                    if platform_insight:
                        insights.append(platform_insight)

            self.log.info(f"竞品洞察收集完成，共获取 {len(insights)} 条洞察")
        except Exception as e:
            self.log.error(f"竞品洞察失败: {e}")
        return insights

    async def _extract_platform_insight(self, platform_name: str, search_result: dict, rank: int) -> dict:
        """
        从搜索结果中提取平台洞察

        :param platform_name: 平台名称
        :param search_result: 搜索结果项
        :param rank: 排名序号
        :return: 结构化洞察数据
        """
        try:
            summary = search_result.get("title", "")
            content = search_result.get("content", "")

            # 使用LLM提取关键论点和结构
            system_prompt = f"""
               你是内容分析专家，请分析来自{platform_name}平台的内容。

               任务：
               1. 提取核心论点（2-3个）
               2. 分析内容结构（开篇、主体、结论）
               3. 判断情感倾向
               4. 识别独特视角

               返回JSON格式：
               {{
                   "platform": "{platform_name}",
                   "rank": {rank},
                   "source_summary": "来源摘要（100字内）",
                   "key_arguments": ["论点1", "论点2"],
                   "content_structure": {{
                       "opening": "开篇方式",
                       "main_points": ["要点1", "要点2"],
                       "conclusion": "结论"
                   }},
                   "sentiment": "正面/负面/中性",
                   "unique_angles": ["独特视角1", "独特视角2"],
                   "engagement_estimate": {{
                       "popularity": "高/中/低",
                       "reason": "判断依据"
                   }}
               }}
               """

            user_prompt = f"""
               标题/摘要：{summary}
               内容：{content}

               请分析上述内容并返回JSON格式结果。
               """

            client = self.llm.create_async_client("deepseek-flash")
            analysis_text, _ = await self.llm.get_response_from_llm_async(
                user_prompt=user_prompt,
                client=client,
                system_prompt=system_prompt,
                temperature=0.3,
                model="deepseek-flash"
            )

            # 解析JSON
            try:
                insight_data = extract_json_between_markers(analysis_text)
                return insight_data
            except Exception as e:
                self.log.error(f"解析平台洞察JSON失败: {e}")
                # 返回简化版本
                return {
                    "platform": platform_name,
                    "rank": rank,
                    "source_summary": summary[:100],
                    "key_arguments": [],
                    "sentiment": "未知",
                    "unique_angles": []
                }

        except Exception as e:
            self.log.error(f"提取平台洞察失败: {e}")
            return None

    async def _extract_data_points(self, hot_title: str, fact_pack: list) -> list:
        """从事实包中提取可量化的数据点"""
        data_points = []

        try:
            # 简单正则匹配数字和百分比
            import re
            pattern = r'(\d+\.?\d*)%|(\d+\.?\d*)(?:万|千|百|亿)?[个项次篇部]'

            for fact_item in fact_pack:
                content = fact_item.get("fact", "")
                matches = re.findall(pattern, content)

                for match in matches:
                    value = match[0] if match[0] else match[1]
                    if value:
                        data_points.append({
                            "value": f"{value}%" if "%" in content else value,
                            "context": content[:100] + "..." if len(content) > 100 else content,
                            "source": fact_item.get("source", "")
                        })

        except Exception as e:
            self.log.error(f"数据点提取失败: {e}")

        return data_points
