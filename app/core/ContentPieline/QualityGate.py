import json
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from app.core.AiAgent.llm import LLM, extract_json_between_markers
from app.tools.LoggingConfig import LoggingConfig
from app.core.config_manager import config


class ReviewStatus(Enum):
    """评审状态"""
    PASS = "pass"  # 通过
    REVISE = "revise"  # 需要修改
    REJECT = "reject"  # 拒绝（需重写）


@dataclass
class ExpertReview:
    """专家评审结果"""
    expert_name: str  # 专家名称
    expert_role: str  # 专家角色描述
    score: float  # 该专家打分 (1-10)
    passed: bool  # 是否通过该专家标准
    comments: List[str]  # 专业评语
    suggestions: List[str]  # 改进建议
    confidence: float = 0.8  # 置信度 (0-1)


@dataclass
class QualityScore:
    """质量评分数据类"""
    handwriting_score: float = 0.0  # 手写感 (1-10)
    information_density: float = 0.0  # 信息密度 (1-10)
    viewpoint_uniqueness: float = 0.0  # 观点独特性 (1-10)
    structure_readability: float = 0.0  # 结构可读性 (1-10)
    platform_adaptation: float = 0.0  # 平台适配度 (1-10)

    @property
    def overall_score(self) -> float:
        """综合得分（可配置权重）"""
        weights = {
            'handwriting_score': 0.30,  # 手写感最重要
            'information_density': 0.25,  # 信息密度次之
            'viewpoint_uniqueness': 0.20,  # 观点独特性
            'structure_readability': 0.15,  # 结构可读性
            'platform_adaptation': 0.10,  # 平台适配度
        }
        return sum([
            self.handwriting_score * weights['handwriting_score'],
            self.information_density * weights['information_density'],
            self.viewpoint_uniqueness * weights['viewpoint_uniqueness'],
            self.structure_readability * weights['structure_readability'],
            self.platform_adaptation * weights['platform_adaptation'],
        ])

    def to_dict(self) -> dict:
        return {
            **asdict(self),
            'overall_score': self.overall_score
        }


@dataclass
class QualityReport:
    """质量评估报告（增强版）"""
    score: QualityScore
    issues: List[str]
    suggestions: List[str]
    ai_trace_indicators: List[str]
    strengths: List[str]
    passed: bool

    # 新增：多专家评审详情
    expert_reviews: List[ExpertReview] = None
    review_status: ReviewStatus = ReviewStatus.PASS
    final_verdict: str = ""  # 最终裁决说明


class ContentAnalyzer:
    """内容分析专家 - 评估信息密度和观点独特性"""

    def __init__(self, platform: str):
        self.platform = platform
        self.log = LoggingConfig(
            log_file_path=config.logfile_path,
            log_level=config.log_level
        ).get_logger(f"Expert.ContentAnalyzer.{platform}")
        self.llm = LLM()

    async def review(self, content: str, title: str) -> ExpertReview:
        system_prompt = f"""
        你是{self.platform}平台的资深内容分析专家，专注于评估：
        1. 信息密度：内容是否有实质性干货，还是空洞的废话
        2. 观点独特性：是否有鲜明的个人见解，还是人云亦云
        3. 论据支撑：观点是否有案例、数据、经历支撑
        
        评分标准：
        - 9-10分：信息密集，观点独到，论据充分
        - 7-8分：有一定信息量，观点清晰
        - 5-6分：信息稀疏，观点平庸
        - 1-4分：纯车轱辘话，毫无价值
        
        请返回JSON格式：
        {{
            "score": 7.5,
            "passed": true,
            "comments": ["评语1", "评语2"],
            "suggestions": ["建议1", "建议2"],
            "confidence": 0.85
        }}
        """

        user_prompt = f"""
        标题：{title}
        内容：
        {content[:2500]}
        
        请从内容分析角度进行评审。
        """

        return await self._execute_review(system_prompt, user_prompt, "内容分析专家", "评估信息密度与观点独特性")


class HookAnalyzer:
    """钩子分析专家 - 评估标题和开篇吸引力"""

    def __init__(self, platform: str):
        self.platform = platform
        self.log = LoggingConfig(
            log_file_path=config.logfile_path,
            log_level=config.log_level
        ).get_logger(f"Expert.HookAnalyzer.{platform}")
        self.llm = LLM()

    async def review(self, content: str, title: str) -> ExpertReview:
        system_prompt = f"""
        你是{self.platform}平台的钩子分析专家，专注于评估：
        1. 标题吸引力：是否能激发点击欲望，但不标题党
        2. 开篇抓力：前3行是否能留住读者
        3. 共鸣感：是否能快速建立情感连接
        
        评分标准：
        - 9-10分：标题惊艳，开篇即抓住注意力
        - 7-8分：标题合格，开篇有吸引力
        - 5-6分：标题平淡，开篇一般
        - 1-4分：标题无聊，开篇劝退
        
        请返回JSON格式：
        {{
            "score": 7.5,
            "passed": true,
            "comments": ["评语1", "评语2"],
            "suggestions": ["建议1", "建议2"],
            "confidence": 0.85
        }}"""

        user_prompt = f"""
        标题：{title}
        内容（重点关注前200字）：
        {content[:500]}
        
        请从钩子设计角度进行评审。
        """

        return await self._execute_review(system_prompt, user_prompt, "钩子分析专家", "评估标题与开篇吸引力")


class StructureExpert:
    """架构专家 - 评估结构和可读性"""

    def __init__(self, platform: str):
        self.platform = platform
        self.log = LoggingConfig(
            log_file_path=config.logfile_path,
            log_level=config.log_level
        ).get_logger(f"Expert.StructureExpert.{platform}")
        self.llm = LLM()

    async def review(self, content: str, title: str) -> ExpertReview:
        system_prompt = f"""
        你是{self.platform}平台的内容架构专家，专注于评估：
        1. 逻辑流畅性：论点展开是否自然
        2. 段落节奏：长短搭配是否舒适
        3. 视觉友好度：排版、分段、重点标注
        4. 结尾力度：收尾是否有力，是否引导互动
        
        评分标准：
        - 9-10分：结构精妙，阅读体验极佳
        - 7-8分：结构清晰，易于理解
        - 5-6分：结构松散，需要努力阅读
        - 1-4分：逻辑混乱，难以跟进
        
        请返回JSON格式：
        {{
            "score": 7.5,
            "passed": true,
            "comments": ["评语1", "评语2"],
            "suggestions": ["建议1", "建议2"],
            "confidence": 0.85
        }}"""

        user_prompt = f"""
        标题：{title}
        完整内容：
        {content[:3000]}
        
        请从内容架构角度进行评审。
        """

        return await self._execute_review(system_prompt, user_prompt, "架构专家", "评估结构与可读性")


class PlatformFitExpert:
    """平台适配专家 - 评估社区文化匹配度"""

    def __init__(self, platform: str):
        self.platform = platform
        self.log = LoggingConfig(
            log_file_path=config.logfile_path,
            log_level=config.log_level
        ).get_logger(f"Expert.PlatformFitExpert.{platform}")
        self.llm = LLM()

        self.platform_characteristics = {
            "zhihu": {
                "tone": "理性讨论，真诚分享",
                "style": "深度分析+个人体感",
                "taboos": ["营销味", "鸡汤文", "搬运洗稿"]
            },
            "weibo": {
                "tone": "轻松活泼，热点跟随",
                "style": "短平快+情绪共鸣",
                "taboos": ["长篇大论", "过于严肃", "缺乏话题性"]
            }
        }

    async def review(self, content: str, title: str) -> ExpertReview:
        characteristics = self.platform_characteristics.get(self.platform, {})
        tone = characteristics.get("tone", "通用")
        style = characteristics.get("style", "通用")
        taboos = ", ".join(characteristics.get("taboos", []))

        system_prompt = f"""
        你是{self.platform}平台的社区文化专家，专注于评估：
        1. 语气风格：是否符合平台调性（期望：{tone}）
        2. 表达方式：是否贴合用户习惯（期望：{style}）
        3. 禁忌规避：是否触犯平台雷区（避免：{taboos}）
        4. 互动潜力：是否能激发评论和转发
        
        评分标准：
        - 9-10分：完美融入社区，像原生用户创作
        - 7-8分：基本符合平台风格
        - 5-6分：有明显违和感
        - 1-4分：完全不适合该平台
        
        请返回JSON格式：
        {{
            "score": 7.5,
            "passed": true,
            "comments": ["评语1", "评语2"],
            "suggestions": ["建议1", "建议2"],
            "confidence": 0.85
        }}
        """

        user_prompt = f"""
        标题：{title}
        内容：
        {content[:2500]}
        
        请从平台适配角度进行评审。
        """

        return await self._execute_review(system_prompt, user_prompt, "平台适配专家", "评估社区文化匹配度")


class ChiefEditor:
    """主编审 - 综合各专家意见，做出最终裁决"""

    def __init__(self, platform: str):
        self.platform = platform
        self.log = LoggingConfig(
            log_file_path=config.logfile_path,
            log_level=config.log_level
        ).get_logger(f"Expert.ChiefEditor.{platform}")
        self.llm = LLM()

    async def make_verdict(self,
                           expert_reviews: List[ExpertReview],
                           ai_traces: List[str],
                           content_length: int) -> Tuple[ReviewStatus, str, List[str]]:
        """
        综合评审

        Returns:
            (评审状态, 裁决说明, 最终建议列表)
        """
        scores = [r.score for r in expert_reviews]
        avg_score = sum(scores) / len(scores) if scores else 0
        min_score = min(scores) if scores else 0
        failed_experts = [r for r in expert_reviews if not r.passed]

        # 收集所有建议
        all_suggestions = []
        for review in expert_reviews:
            all_suggestions.extend(review.suggestions[:2])  # 每个专家最多取2条

        # 规则引擎初步判断
        if avg_score >= 8.0 and len(failed_experts) == 0:
            status = ReviewStatus.PASS
            verdict = f"优秀作品！综合评分{avg_score:.1f}，所有专家均认可。"
        elif avg_score >= 6.5 and len(failed_experts) <= 1:
            status = ReviewStatus.REVISE
            verdict = f"需要修改。综合评分{avg_score:.1f}，{len(failed_experts)}位专家提出质疑。"
        else:
            status = ReviewStatus.REJECT
            verdict = f"建议重写。综合评分{avg_score:.1f}，{len(failed_experts)}位专家不通过。"

        # AI痕迹扣分
        if ai_traces:
            verdict += f" 检测到{len(ai_traces)}个AI痕迹。"
            if len(ai_traces) > 3:
                status = ReviewStatus.REVISE if status == ReviewStatus.PASS else status

            # 篇幅检查
        if content_length < 200:
            verdict += " 篇幅过短。"
            status = ReviewStatus.REVISE if status == ReviewStatus.PASS else status
        elif content_length > 3000:
            verdict += " 篇幅过长。"

        return status, verdict, all_suggestions[:5]  # 最多5条建议

    async def _execute_review(self, system_prompt: str, user_prompt: str,
                              expert_name: str, expert_role: str) -> ExpertReview:
        """执行专家评审（复用逻辑）"""
        try:
            client = self.llm.create_async_client("deepseek-flash")
            response, _ = await self.llm.get_response_from_llm_async(
                user_prompt=user_prompt,
                client=client,
                model="deepseek-chat",
                system_prompt=system_prompt,
                temperature=0.2
            )

            review_data = extract_json_between_markers(response)
            if review_data:
                return ExpertReview(
                    expert_name=expert_name,
                    expert_role=expert_role,
                    score=float(review_data.get('score', 5.0)),
                    passed=bool(review_data.get('passed', False)),
                    comments=review_data.get('comments', []),
                    suggestions=review_data.get('suggestions', []),
                    confidence=float(review_data.get('confidence', 0.8))
                )
        except Exception as e:
            self.log.error(f"{expert_name}评审失败: {e}")

        # 降级返回
        return ExpertReview(
            expert_name=expert_name,
            expert_role=expert_role,
            score=5.0,
            passed=False,
            comments=["评审异常，使用默认评分"],
            suggestions=["请人工复核"],
            confidence=0.3
        )


class QualityGate:
    """
    质量评估器 — 多专家评审机制（四维评分）

    核心设计：
    1. 两阶段评审：快速初筛 + 深度专家评审
    2. 四位专家独立评审：内容、钩子、架构、平台适配
    3. 主编审综合裁决：汇总意见，给出最终决策
    4. 迭代优化闭环：不通过则提供具体修改建议
    """

    def __init__(self, platform: str = "zhihu", enable_multi_expert: bool = True):
        """
        初始化质量评估器

        :param platform: 平台类型（zhihu/weibo）
        :param enable_multi_expert: 是否启用多专家评审（True/False）
        """
        self.log = LoggingConfig(
            log_file_path=config.logfile_path,
            log_level=config.log_level
        ).get_logger(f"{self.__class__.__name__}.{platform}")

        self.llm = LLM()
        self.platform = platform
        self.enable_multi_expert = enable_multi_expert

        # 初始化专家团队
        if enable_multi_expert:
            self.content_analyzer = ContentAnalyzer(platform)
            self.hook_analyzer = HookAnalyzer(platform)
            self.structure_expert = StructureExpert(platform)
            self.platform_fit_expert = PlatformFitExpert(platform)
            self.chief_editor = ChiefEditor(platform)

        # AI痕迹关键词库
        self.ai_trace_patterns = [
            r'首先.*其次.*最后',
            r'综上所述|总而言之',
            r'值得注意的是|需要强调的是',
            r'从.*角度来看',
            r'不仅.*而且.*还',
            r'随着.*的发展',
            r'在当今.*时代',
        ]

    async def evaluate(self, content: str, title: str = "",
                       original_prompt: str = "",
                       competitor_samples: List[str] = None) -> QualityReport:
        """
        全面评估生成内容的质量（多专家评审版）
        """
        self.log.info(f"开始质量评估 - 平台: {self.platform}, 内容长度: {len(content)}")

        # ===== 第一阶段：快速初筛 =====
        ai_traces = self._detect_ai_traces(content)
        quick_issues = self._quick_check(content, ai_traces)

        # 如果初筛发现严重问题，直接返回
        if len(quick_issues) > 3:
            self.log.warning(f"初筛发现{len(quick_issues)}个问题，跳过专家评审")
            return self._build_quick_reject_report(content, quick_issues, ai_traces)

        # ===== 第二阶段：多专家评审 =====
        if self.enable_multi_expert:
            expert_reviews = await self._multi_expert_review(content, title)

            # 主编审综合裁决
            status, verdict, final_suggestions = await self.chief_editor.make_verdict(
                expert_reviews, ai_traces, len(content)
            )
            # 提取优点
            strengths = self._extract_strengths_from_reviews(expert_reviews)

            # 构建综合评分（兼容旧接口）
            score = self._aggregate_scores(expert_reviews)

            # 判断是否通过
            passed = (status == ReviewStatus.PASS)

            report = QualityReport(
                score=score,
                issues=self._collect_issues(expert_reviews, ai_traces),
                suggestions=final_suggestions,
                ai_trace_indicators=ai_traces,
                strengths=strengths,
                passed=passed,
                expert_reviews=expert_reviews,
                review_status=status,
                final_verdict=verdict
            )
        else:
            # 降级为单评估器模式
            report = await self._single_evaluator_evaluate(content, title, ai_traces)

        self.log.info(
            f"质量评估完成 - 状态: {report.review_status.value}, "
            f"综合得分: {report.score.overall_score:.2f}/10"
        )

        return report

    async def _multi_expert_review(self, content: str, title: str) -> List[ExpertReview]:
        """并行执行多位专家评审"""
        import asyncio

        tasks = [
            self.content_analyzer.review(content, title),
            self.hook_analyzer.review(content, title),
            self.structure_expert.review(content, title),
            self.platform_fit_expert.review(content, title),
        ]

        reviews = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理异常
        valid_reviews = []
        for i, review in enumerate(reviews):
            if isinstance(review, Exception):
                self.log.error(f"专家{i}评审异常: {review}")
            else:
                valid_reviews.append(review)

        return valid_reviews

    def _quick_check(self, content: str, ai_traces: List[str]) -> List[str]:
        """快速初筛检查"""
        issues = []

        # AI痕迹过多
        if len(ai_traces) > 3:
            issues.append(f"AI痕迹过多（{len(ai_traces)}个）")

        # 篇幅异常
        if len(content) < 100:
            issues.append("篇幅过短（<100字）")
        elif len(content) > 5000:
            issues.append("篇幅过长（>5000字）")

        # 明显格式问题
        if content.count('#') > 10:
            issues.append("Markdown标题过多，可能格式混乱")

        return issues

    def _build_quick_reject_report(self, content: str, issues: List[str],
                                   ai_traces: List[str]) -> QualityReport:
        """构建快速拒绝报告"""
        return QualityReport(
            score=QualityScore(),
            issues=issues,
            suggestions=["建议重新生成内容，确保符合基本要求"],
            ai_trace_indicators=ai_traces,
            strengths=[],
            passed=False,
            expert_reviews=[],
            review_status=ReviewStatus.REJECT,
            final_verdict=f"初筛未通过：{'; '.join(issues)}"
        )

    async def _single_evaluator_evaluate(self, content: str, title: str,
                                         ai_traces: List[str]) -> QualityReport:
        """单评估器模式（兼容旧逻辑）"""
        score = await self._multi_dimension_scoring(content, title)
        issues = self._diagnose_issues(content, score, ai_traces)
        suggestions = await self._generate_suggestions(content, score, issues)
        strengths = self._extract_strengths(content, score)
        passed = self._check_pass_criteria(score, issues)

        return QualityReport(
            score=score,
            issues=issues,
            suggestions=suggestions,
            ai_trace_indicators=ai_traces,
            strengths=strengths,
            passed=passed,
            expert_reviews=[],
            review_status=ReviewStatus.PASS if passed else ReviewStatus.REVISE,
            final_verdict="单评估器模式"
        )

    def _aggregate_scores(self, expert_reviews: List[ExpertReview]) -> QualityScore:
        """将专家评审结果聚合为传统评分格式"""
        if not expert_reviews:
            return QualityScore()

        # 映射专家到评分维度
        score_mapping = {
            "内容分析专家": ["information_density", "viewpoint_uniqueness"],
            "钩子分析专家": ["handwriting_score"],
            "架构专家": ["structure_readability"],
            "平台适配专家": ["platform_adaptation"],
        }

        score_dict = {}
        for review in expert_reviews:
            dimensions = score_mapping.get(review.expert_name, [])
            for dim in dimensions:
                score_dict[dim] = review.score

        return QualityScore(
            handwriting_score=score_dict.get('handwriting_score', 5.0),
            information_density=score_dict.get('information_density', 5.0),
            viewpoint_uniqueness=score_dict.get('viewpoint_uniqueness', 5.0),
            structure_readability=score_dict.get('structure_readability', 5.0),
            platform_adaptation=score_dict.get('platform_adaptation', 5.0),
        )

    def _collect_issues(self, expert_reviews: List[ExpertReview],
                        ai_traces: List[str]) -> List[str]:
        """收集所有专家指出的问题"""
        issues = list(ai_traces)

        for review in expert_reviews:
            if not review.passed:
                issues.extend([f"[{review.expert_name}] {c}" for c in review.comments])

        return issues

    def _extract_strengths_from_reviews(self, expert_reviews: List[ExpertReview]) -> List[str]:
        """从专家评审中提取优点"""
        strengths = []

        for review in expert_reviews:
            if review.score >= 8.0:
                strengths.append(f"[{review.expert_name}] {review.comments[0] if review.comments else '表现优秀'}")

        return strengths

    def _detect_ai_traces(self, content: str) -> List[str]:
        """
        检测AI痕迹指标

        Returns:
            AI痕迹指标列表
        """
        traces = []

        # 1. 检测模板化结构词
        for pattern in self.ai_trace_patterns:
            matches = re.findall(pattern, content)
            if matches:
                traces.append(f"发现模板化表达: '{matches[0]}'")

        # 2. 检测过度工整的段落长度
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        if paragraphs:
            lengths = [len(p) for p in paragraphs]
            avg_len = sum(lengths) / len(lengths)
            variance = sum((l - avg_len) ** 2 for l in lengths) / len(lengths)
            std_dev = variance ** 0.5

            # 如果标准差很小，说明段落长度过于均匀（AI特征）
            if std_dev < avg_len * 0.15 and len(paragraphs) > 3:
                traces.append("段落长度过于均匀（标准差={:.0f}），缺乏自然变化".format(std_dev))

        # 3. 检测缺乏个人代词
        personal_pronouns = ['我', '我的', '我觉得', '我认为', '我身边', '我朋友']
        has_personal = any(pronoun in content for pronoun in personal_pronouns)
        if not has_personal and len(content) > 300:
            traces.append("缺乏第一人称视角，缺少个人体感表达")

        # 4. 检测过度使用连接词
        connectors = ['然而', '因此', '所以', '但是', '不过', '尽管']
        connector_count = sum(content.count(c) for c in connectors)
        if connector_count > len(content) / 100:
            traces.append("连接词使用频率过高（{}次），显得生硬".format(connector_count))

        # 5. 检测缺乏口语化表达
        colloquial_patterns = ['吧', '呢', '嘛', '啊', '呀', '说实话', '讲真', '其实']
        has_colloquial = any(pattern in content for pattern in colloquial_patterns)
        if not has_colloquial and len(content) > 200:
            traces.append("缺乏口语化语气词，书面感过强")

        return traces

    async def _multi_dimension_scoring(self, content: str, title: str,
                                       competitor_samples: List[str] = None) -> QualityScore:
        """
        使用LLM进行多维度评分
        """
        try:
            system_prompt = f"""
            你是{self.platform}平台的资深内容质量评估专家。
            请从以下5个维度对内容进行严格打分（1-10分）：
    
            1. **手写感**：是否像真人写的？有无AI模板痕迹？是否有个人体感和口语化表达？
            2. **信息密度**：是否有干货？还是纯车轱辘话？信息价值如何？
            3. **观点独特性**：是否有鲜明个人观点？还是人云亦云？
            4. **结构可读性**：排版、分段、节奏是否舒适？
            5. **平台适配度**：是否符合{self.platform}社区氛围和用户期待？
            
            评分标准：
            - 1-3分：严重不足
            - 4-6分：及格但有明显缺陷
            - 7-8分：良好
            - 9-10分：优秀
            
            请返回严格的JSON格式，不要任何解释文字。
            """

            # 处理竞品样本（避免在f-string中使用反斜杠）
            competitor_text = ""
            if competitor_samples:
                samples_joined = '\n---\n'.join(competitor_samples[:2])
                competitor_text = f"竞品参考样本：\n{samples_joined}"

            user_prompt = f"""
            请评估以下内容：
            标题：{title if title else '无标题'}

            内容：
            {content[:3000]}

            {competitor_text}

            返回格式：
            {{
                "handwriting_score": 7.5,
                "information_density": 8.0,
                "viewpoint_uniqueness": 6.5,
                "structure_readability": 8.5,
                "platform_adaptation": 7.0,
                "brief_reasoning": "简短评分理由"
            }}
            """

            client = self.llm.create_async_client("deepseek-flash")
            response, _ = await self.llm.get_response_from_llm_async(
                user_prompt=user_prompt,
                client=client,
                model="deepseek-chat",
                system_prompt=system_prompt,
                temperature=0.2  # 低温度保证评分稳定性
            )

            # 从响应中提取JSON
            try:
                score_data = extract_json_between_markers(response)
                return QualityScore(
                    handwriting_score=float(score_data.get('handwriting_score', 5.0)),
                    information_density=float(score_data.get('information_density', 5.0)),
                    viewpoint_uniqueness=float(score_data.get('viewpoint_uniqueness', 5.0)),
                    structure_readability=float(score_data.get('structure_readability', 5.0)),
                    platform_adaptation=float(score_data.get('platform_adaptation', 5.0)),
                )
            except (json.JSONDecodeError, ValueError) as e:
                self.log.warning(f"评分JSON解析失败: {e}，使用默认评分")
                return QualityScore()

        except Exception as e:
            self.log.error(f"多维度评分失败: {e}")
            return QualityScore()

    def _diagnose_issues(self, content: str, score: QualityScore,
                         ai_traces: List[str]) -> List[str]:
        """
        诊断内容问题
        """
        issues = []

        # 基于AI痕迹
        if ai_traces:
            issues.extend(ai_traces)

        # 基于评分阈值
        if score.handwriting_score < 6.0:
            issues.append("手写感不足：AI痕迹明显，缺乏真人交流感")

        if score.information_density < 6.0:
            issues.append("信息密度低：内容空洞，缺乏实质性干货")

        if score.viewpoint_uniqueness < 6.0:
            issues.append("观点平庸：缺乏独特见解，容易淹没在同类内容中")

        if score.structure_readability < 6.0:
            issues.append("结构混乱：排版不佳，阅读体验差")

        if score.platform_adaptation < 6.0:
            issues.append(f"平台适配差：不符合{self.platform}社区调性")

        # 基于内容特征检测
        if len(content) < 200:
            issues.append("篇幅过短：难以展开深度讨论")

        if len(content) > 3000:
            issues.append("篇幅过长：可能影响完读率")

        # 检测缺乏互动元素
        if self.platform == "zhihu":
            if not any(phrase in content for phrase in ['大家', '你们', '你觉得', '有没有']):
                issues.append("缺乏互动引导：未激发读者评论欲望")

        return issues

    async def _generate_suggestions(self, content: str, score: QualityScore, issues: List[str]) -> List[str]:
        """
        生成具体的改进建议（使用LLM）
        :param content: 内容文本
        :param score: 内容质量评分
        :param issues: 诊断出的问题列表
        :return: 改进建议列表
        """
        try:
            system_prompt = f"""
            你是内容优化专家。根据发现的问题，给出具体、可操作的改进建议。
            每条建议必须：
            1. 明确指出要改什么
            2. 给出改写示例或方向
            3. 简洁明了，不超过50字
            
            不要泛泛而谈，要针对性强。
            """

            user_prompt = f"""
            内容问题诊断：
            {chr(10).join(f'- {issue}' for issue in issues[:5])}
            
            当前内容片段：
            {content[:500]}
            
            请给出3-5条最关键的改进建议，按优先级排序。返回JSON数组格式：
            ["建议1", "建议2", "建议3"]
            """
            client = self.llm.create_async_client("deepseek-flash")
            response, _ = await self.llm.get_response_from_llm_async(
                user_prompt=user_prompt,
                client=client,
                model="deepseek-chat",
                system_prompt=system_prompt,
                temperature=0.5
            )

            try:
                suggestions = extract_json_between_markers(response)
                if isinstance(suggestions, list):
                    return suggestions[:5]  # 最多5条
            except:
                pass

            # 降级：返回通用建议
            return self._fallback_suggestions(issues)
        except Exception as e:
            self.log.error(f"生成建议失败: {e}")
            return self._fallback_suggestions(issues)

    def _extract_strengths(self, content: str, score: QualityScore) -> List[str]:
        """提取内容优点"""
        strengths = []

        if score.handwriting_score >= 8.0:
            strengths.append("手写感强：表达自然，像真人交流")

        if score.information_density >= 8.0:
            strengths.append("信息密度高：干货满满，有参考价值")

        if score.viewpoint_uniqueness >= 8.0:
            strengths.append("观点独特：有鲜明的个人见解")

        if score.structure_readability >= 8.0:
            strengths.append("结构清晰：排版舒适，易于阅读")

        if score.platform_adaptation >= 8.0:
            strengths.append(f"平台适配好：符合{self.platform}社区氛围")

            # 检测具体优点
        if any(word in content for word in ['案例', '例子', '比如', '例如']):
            strengths.append("使用了具体案例支撑观点")

        if any(word in content for word in ['数据', '%', '统计', '调研']):
            strengths.append("引用了数据增强说服力")

        return strengths

    def _check_pass_criteria(self, score: QualityScore, issues: List[str]) -> bool:
        """
        判断是否通过质检

        通过标准：
        1. 综合得分 >= 7.0
        2. 手写感 >= 6.5（核心指标）
        3. 严重问题数量 <= 2
        """
        severe_issues = len([i for i in issues if any(
            keyword in i for keyword in ['严重', '不足', '缺乏', '空洞']
        )])

        return (
                score.overall_score >= 7.0 and
                score.handwriting_score >= 6.5 and
                severe_issues <= 2
        )

    async def _apply_optimizations(self, content: str, title: str,
                                   suggestions: List[str]) -> str:
        """
        应用优化建议生成新版本
        """
        try:
            system_prompt = f"""你是{self.platform}平台的优质内容创作者。
            根据评估建议，对内容进行针对性优化。
    
            优化原则：
            1. 保持原有核心观点和信息
            2. 针对性解决指出的问题
            3. 增强手写感和个人体感
            4. 输出完整的优化后内容"""

            user_prompt = f"""原标题：{title}
    
            原内容：
            {content}
    
            评估建议：
            {chr(10).join(f'{i + 1}. {s}' for i, s in enumerate(suggestions))}
    
            请输出优化后的完整内容（Markdown格式），不要解释修改了什么。
            """

            client = self.llm.create_async_client("deepseek-chat")
            optimized, _ = await self.llm.get_response_from_llm_async(
                user_prompt=user_prompt,
                client=client,
                model="deepseek-chat",
                system_prompt=system_prompt,
                temperature=0.7
            )

            return optimized
        except Exception as e:
            self.log.error(f"优化内容失败: {e}")
            return content

    async def optimize_content(self, content: str, title: str = "",
                               max_iterations: int = 3) -> Tuple[str, List[QualityReport]]:
        """
        自动迭代优化内容

        Args:
            content: 原始内容
            title: 标题
            max_iterations: 最大迭代次数

        Returns:
            (优化后的内容, 历次评估报告)
        """
        reports = []
        current_content = content

        for iteration in range(max_iterations):
            self.log.info(f"第 {iteration + 1}/{max_iterations} 轮优化")

            # 评估当前版本
            report = await self.evaluate(current_content, title)
            reports.append(report)

            # 如果通过质检，提前退出
            if report.passed:
                self.log.info(f"✓ 第 {iteration + 1} 轮通过质检，综合得分: {report.score.overall_score:.2f}")
                break

            # 生成优化后的内容
            current_content = await self._apply_optimizations(
                current_content, title, report.suggestions
            )

        return current_content, reports
