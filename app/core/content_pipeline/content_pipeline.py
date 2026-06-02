"""
内容生成流水线

提供多种内容生成策略，由 Writer 层调用
实现: 信息增强 → 风格锚定 → 创作生成 → 质检评估 → 迭代优化的完整链路
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from playwright.async_api import BrowserContext, Page

from app.core.ai_agent.llm import LLM, extract_json_between_markers
from app.core.mcp import MCPIntegration
from app.core.prompt_manager import get_prompt_manager
from app.core.content_pipeline.info_enricher import InfoEnricher
from app.core.content_pipeline.quality_gate import QualityGate
from app.core.config_manager import config
from app.tools.logging_config import LoggingConfig


class BaseContentPipeline(ABC):
    """内容生成流水线基类"""

    def __init__(self, platform_name: str = "zhihu"):
        self.log = LoggingConfig(
            log_file_path=config.logfile_path,
            log_level=config.log_level
        ).get_logger(self.__class__.__name__)

        self.platform_name = platform_name
        self.model_name = config.platforms[platform_name]['model'].get("name", "deepseek-chat")
        self.temperature = config.platforms[platform_name]['model'].get("temperature", 0.7)

        self.llm = LLM()
        self.client = self.llm.create_async_client(self.model_name)
        self.prompt_mgr = get_prompt_manager()

    @abstractmethod
    async def generate(
            self,
            user_prompt: str,
            system_prompt: str,
            temperature: float = None,
            max_iterations: int = 50,
            **kwargs
    ) -> Tuple[Any, List[Dict]]:
        """
        生成内容的核心方法

        Args:
            user_prompt: 用户提示词
            system_prompt: 系统提示词
            temperature: 温度参数，None 则使用默认值
            max_iterations: 最大迭代次数
            **kwargs: 其他扩展参数

        Returns:
            (生成的内容, 消息历史)
        """
        pass


class SimpleContentPipeline(BaseContentPipeline):
    """
    简单生成流水线

    直接调用 LLM + MCP 工具一次性生成内容，无增强和质检
    """

    async def generate(
            self,
            user_prompt: str,
            system_prompt: str,
            temperature: float = None,
            **kwargs
    ) -> Tuple[Any, List[Dict]]:
        """
        简单生成：单次 LLM 调用

        Args:
            user_prompt: 用户提示词
            system_prompt: 系统提示词
            temperature: 温度参数

        Returns:
            (生成的内容, 消息历史)
        """
        if temperature is None:
            temperature = self.temperature

        self.log.info(f"📝 [SimplePipeline] 开始简单生成")

        result, msg_history = await self.llm.get_response_from_llm_async(
            user_prompt=user_prompt,
            client=self.client,
            model=self.model_name,
            system_prompt=system_prompt,
            temperature=temperature
        )

        self.log.info(f"✅ [SimplePipeline] 生成完成")

        return result, msg_history


class EnhancedContentPipeline(BaseContentPipeline):
    """
    增强生成流水线

    完整五阶段链路：
    1. 信息增强 - 使用 InfoEnricher 搜集背景资料
    2. 风格锚定 - 确定写作风格和角度
    3. 创作生成 - 基于增强信息生成初稿
    4. 质检评估 - 使用 QualityGate 评估质量
    5. 迭代优化 - 根据评估结果自动优化
    """

    def __init__(
            self,
            platform_name: str = "zhihu",
            enable_enrichment: bool = True,
            enable_quality_check: bool = True,
            quality_threshold: float = 7.0,
            max_optimization_rounds: int = 2,
            page: Optional[Page] = None
    ):
        """
        初始化增强流水线

        Args:
            platform_name: 平台名称
            enable_enrichment: 是否启用信息增强
            enable_quality_check: 是否启用质检和优化
            quality_threshold: 质量通过阈值
            max_optimization_rounds: 最大优化轮数
        """
        super().__init__(platform_name)
        self.enable_enrichment = enable_enrichment
        self.enable_quality_check = enable_quality_check

        # 初始化 InfoEnricher
        self.info_enricher = InfoEnricher(page=page) if enable_enrichment else None

        # 初始化 QualityGate
        self.quality_gate = QualityGate(
            platform=platform_name,
            enable_multi_expert=True
        ) if enable_quality_check else None

        self.quality_threshold = quality_threshold
        self.max_optimization_rounds = max_optimization_rounds

    async def generate(
            self,
            user_prompt: str,
            system_prompt: str,
            temperature: float = None,
            **kwargs
    ) -> Tuple[Any, List[Dict]]:
        """
        增强生成：完整的五阶段流水线

        Args:
            user_prompt: 用户提示词（应包含 hot_title 和 hot_content 信息）
            system_prompt: 系统提示词
            temperature: 温度参数
            **kwargs: 额外参数
                - hot_title: 热点标题（用于信息增强）
                - hot_content: 热点内容列表（用于信息增强）
                - title: 文章标题（用于质检）

        Returns:
            (生成的内容, 消息历史)
        """
        if temperature is None:
            temperature = self.temperature

        hot_title = kwargs.get('hot_title', '')
        hot_content = kwargs.get('hot_content', [])
        title = kwargs.get('title', hot_title)

        self.log.info(f"🚀 [EnhancedPipeline] 开始增强生成流程")
        self.log.info(f"   标题: {title}")
        self.log.info(f"   配置: 增强={self.enable_enrichment}, 质检={self.enable_quality_check}")

        try:
            current_user_prompt = user_prompt
            msg_history = []

            # ===== 阶段1: 信息增强 =====
            if self.enable_enrichment and self.info_enricher and hot_title:
                self.log.info("📊 [阶段1/5] 信息增强...")
                enriched_prompt, history_entry = await self._enrich_information(
                    current_user_prompt,
                    hot_title,
                    hot_content
                )
                current_user_prompt = enriched_prompt
                msg_history.extend(history_entry)
            else:
                self.log.info("⏭️ 跳过信息增强")

            # ===== 阶段2: 风格锚定 =====
            self.log.info("🎯 [阶段2/5] 风格锚定...")
            styled_prompt, style_history = await self._anchor_style(
                current_user_prompt, title
            )
            current_user_prompt = styled_prompt
            msg_history.extend(style_history)

            # ===== 阶段3: 创作生成 =====
            self.log.info("✍️ [阶段3/5] 创作生成...")
            draft_content, draft_history = await self._create_content(
                current_user_prompt, system_prompt, temperature
            )
            msg_history.extend(draft_history)

            # ===== 阶段4 & 5: 质检评估 + 迭代优化 =====
            if self.enable_quality_check and self.quality_gate:
                self.log.info("🔍 [阶段4/5] 质检评估...")
                final_content, optimization_reports = await self._evaluate_and_optimize(
                    draft_content, title, system_prompt, temperature
                )

                # 记录优化报告到消息历史
                if optimization_reports:
                    msg_history.append({
                        "role": "system",
                        "content": f"质检优化完成，共{len(optimization_reports)}轮评估"
                    })
            else:
                final_content = draft_content
                self.log.info("⏭️ 跳过度检优化")

            self.log.info(f"✅ [EnhancedPipeline] 增强生成完成")

            return final_content, msg_history

        except Exception as e:
            self.log.error(f"❌ [EnhancedPipeline] 生成失败: {e}", exc_info=True)
            raise

    async def _enrich_information(
            self,
            original_user_prompt: str,
            hot_title: str,
            hot_content: list
    ) -> Tuple[str, List[Dict]]:
        """
        阶段1: 信息增强

        使用 InfoEnricher 获取结构化素材包，整合到用户提示词中

        Returns:
            (增强后的用户提示词, 消息历史)
        """
        try:
            # 调用 InfoEnricher 获取结构化素材包
            enrichment_data = await self.info_enricher.enrich(hot_title, hot_content)

            # 将增强信息整合到用户提示词中
            topic_analysis = enrichment_data.get('topic_analysis', {})
            fact_pack = enrichment_data.get('fact_pack', [])
            data_points = enrichment_data.get('data_points', [])

            enriched_prompt = f"""
            {original_user_prompt}
    
            【背景信息补充 - 来自信息增强】
    
            📋 主题分析：
            - 分类：{topic_analysis.get('category', '未知')}
            - 关键实体：{', '.join(topic_analysis.get('key_entities', []))}
            - 情感倾向：{topic_analysis.get('sentiment', '中性')}
            - 争议点：{', '.join(topic_analysis.get('controversy_points', []))}
    
            📚 事实资料：
            {self._format_fact_pack(fact_pack)}
    
            📊 可引用数据：
            {self._format_data_points(data_points)}
    
            请结合以上背景信息，创作更有深度和说服力的内容。
            """

            history_entry = {
                "role": "system",
                "content": f"信息增强完成，获取{len(fact_pack)}条事实资料，{len(data_points)}个数据点"
            }

            self.log.info(f"   ✅ 信息增强完成")
            return enriched_prompt, [history_entry]

        except Exception as e:
            self.log.warning(f"   ⚠️ 信息增强失败，使用原始提示词: {e}")
            return original_user_prompt, [{
                "role": "system",
                "content": f"信息增强失败: {str(e)}"
            }]

    async def _anchor_style(
            self,
            user_prompt: str,
            title: str
    ) -> Tuple[str, List[Dict]]:
        """
        阶段2: 风格锚定

        分析需求，确定写作风格、角度和结构

        Returns:
            (带有风格指引的用户提示词, 消息历史)
        """
        try:
            style_prompt = f"""
            请分析以下创作需求，确定最适合的写作策略：

            创作需求：
            {user_prompt[:1000]}

            请确定：
            1. 写作风格（专业分析/通俗易懂/幽默风趣/深度思考等）
            2. 切入角度（技术视角/社会影响/个人经历/数据驱动等）
            3. 文章结构（总分总/对比分析/时间线/问题解决等）
            4. 目标读者群体
            5. 核心观点和立场

            以简洁的要点形式返回，我会将其作为创作的风格指引。
            """

            system_prompt_style = "你是一个专业的内容策划师。分析创作需求特点，制定最佳的写作策略。"

            result, history = await self.llm.get_response_from_llm_async(
                user_prompt=style_prompt,
                client=self.client,
                model=self.model_name,
                system_prompt=system_prompt_style,
                temperature=0.6
            )

            styled_user_prompt = f"""
            【写作风格指引】
            {result}
    
            【创作需求】
            {user_prompt}
    
            请严格按照上述风格指引完成创作。
            """

            self.log.info(f"   ✅ 风格锚定完成")
            return styled_user_prompt, history

        except Exception as e:
            self.log.warning(f"   ⚠️ 风格锚定失败，使用原始提示词: {e}")
        return user_prompt, [{
            "role": "system",
            "content": f"风格锚定失败: {str(e)}"
        }]

    async def _create_content(
            self,
            user_prompt: str,
            system_prompt: str,
            temperature: float
    ) -> Tuple[str, List[Dict]]:
        """
        阶段3: 创作生成

        基于增强后的提示词生成初稿

        Returns:
            (初稿内容, 消息历史)
        """
        result, history = await self.llm.get_response_from_llm_async(
            user_prompt=user_prompt,
            client=self.client,
            model=self.model_name,
            system_prompt=system_prompt,
            temperature=temperature
        )

        self.log.info(f"   ✅ 初稿生成完成，长度: {len(result)}")
        return result, history

    async def _evaluate_and_optimize(
            self,
            content: str,
            title: str,
            system_prompt: str,
            temperature: float
    ) -> Tuple[str, List]:
        """
        阶段4 & 5: 质检评估 + 迭代优化

        使用 QualityGate 评估质量，不达标则自动优化

        Returns:
            (优化后的内容, 历次评估报告)
        """
        try:
            # 使用 QualityGate 进行自动迭代优化
            optimized_content, reports = await self.quality_gate.optimize_content(
                content=content,
                title=title,
                max_iterations=self.max_optimization_rounds
            )
            passed_count = sum(1 for r in reports if r.passed)
            self.log.info(f"   ✅ 质检优化完成，{passed_count}/{len(reports)}轮通过")
        except Exception as e:
            self.log.error(f"   ❌ 质检优化失败，返回原始内容: {e}")
            return content, []

    @staticmethod
    def _format_fact_pack(fact_pack: list) -> str:
        """格式化事实包"""
        if not fact_pack:
            return "（无额外事实资料）"

        lines = []
        for i, fact in enumerate(fact_pack[:5], 1):  # 限制显示前5条
            source = fact.get('source', '未知来源')
            content = fact.get('fact', '')
            lines.append(f"{i}. [{source}] {content[:200]}")

        return '\n'.join(lines)

    @staticmethod
    def _format_data_points(data_points: list) -> str:
        """格式化数据点"""
        if not data_points:
            return "（无额外数据）"

        lines = []
        for i, data in enumerate(data_points[:5], 1):  # 限制显示前5条
            value = data.get('value', '')
            context = data.get('context', '')
            lines.append(f"{i}. {value} - {context[:150]}")

        return '\n'.join(lines)


# 工厂函数，方便创建不同类型的流水线
def create_pipeline(pipeline_type: str = "simple", **kwargs) -> BaseContentPipeline:
    """
    创建内容生成流水线的工厂函数

    Args:
        pipeline_type: 流水线类型 ("simple" 或 "enhanced")
        **kwargs: 传递给流水线构造函数的额外参数

    Returns:
        BaseContentPipeline 实例
    """
    if pipeline_type == "enhanced":
        return EnhancedContentPipeline(**kwargs)
    elif pipeline_type == "simple":
        return SimpleContentPipeline(**kwargs)
    else:
        raise ValueError(f"未知的流水线类型: {pipeline_type}")


if __name__ == '__main__':
    import asyncio
    import time

    USER_DATA_DIR = r"D:\pythonproject\Ai_Blogger\driver\playwright_data"


    async def main():
        """快速验证 ContentPipeline 的基本功能"""
        from app.core.playwright_driver import AsyncPlaywrightDriver

        print("=" * 60)
        print("  ContentPipeline 快速测试（含浏览器竞品搜索）")
        print("=" * 60)

        async with AsyncPlaywrightDriver(base_data_dir=USER_DATA_DIR) as driver:
            browser, context, page = await driver.launch_browser(
                viewport_type="pc",
                user_data_dir=f"{USER_DATA_DIR}/zhihu_data"
            )

            # ── 1. 工厂函数 ──
            print("\n[1/4] 工厂函数 ...", end=" ")
            try:
                p1 = create_pipeline("simple", platform_name="zhihu")
                p2 = create_pipeline(
                    "enhanced", platform_name="zhihu",
                    enable_quality_check=False, page=page
                )
                assert isinstance(p1, SimpleContentPipeline)
                assert isinstance(p2, EnhancedContentPipeline)
                print("✅")
            except Exception as e:
                print(f"❌ {e}")
                return

            # # ── 2. SimplePipeline ──
            # print("[2/4] SimplePipeline 生成 ...", end=" ")
            # t0 = time.time()
            # try:
            #     content, history = await p1.generate(
            #         user_prompt="为什么越来越多年轻人选择不婚主义？请用一段话回答。",
            #         system_prompt="你是一个接地气的知乎答主，有个人体感，不说空话。",
            #         temperature=0.7,
            #     )
            #     assert content and len(content) > 20
            #     print(f"✅ ({len(content)}字, {time.time() - t0:.1f}s)")
            # except Exception as e:
            #     print(f"❌ {e}")
            #     return

            # ── 3. EnhancedPipeline（带 page，走竞品搜索）─
            print("[3/4] EnhancedPipeline 生成 ...", end=" ")
            t0 = time.time()
            content = "雷军"
            try:
                content2, history2 = await p2.generate(
                    user_prompt=f"基于热点创作一篇知乎短文：\n标题：{content[:30]}",
                    system_prompt="你是一个知乎答主，回答要有深度。",
                    hot_title=content[:30],
                    hot_content=[],
                    temperature=0.7,
                )
                assert content2 and len(content2) > 50
                print(f"✅ ({len(content2)}字, {time.time() - t0:.1f}s, {len(history2)}条消息)")
            except Exception as e:
                print(f"❌ {e}")
                return

            # ── 4. QualityGate ──
            print("[4/4] QualityGate 评估 ...", end=" ")
            t0 = time.time()
            try:
                from app.core.content_pipeline.quality_gate import QualityGate
                gate = QualityGate(platform="zhihu", enable_multi_expert=True)
                report = await gate.evaluate(content=content2, title=content[:30])
                assert report.score.overall_score > 0
                print(f"✅ (综合分{report.score.overall_score:.1f}, "
                      f"{len(report.expert_reviews)}位专家, {time.time() - t0:.1f}s)")
                print(f"   状态: {report.review_status.value} | "
                      f"通过: {'是' if report.passed else '否'}")
                if report.ai_trace_indicators:
                    print(f"   AI痕迹: {report.ai_trace_indicators}")
            except Exception as e:
                print(f"❌ {e}")
                return

        print(f"\n{'=' * 60}")
        print("  全部通过 ✅")
        print(f"{'=' * 60}")


    asyncio.run(main())
