"""
NLP 内容特征分析器

对文本进行表层特征提取和语言风格分析。
依赖 jieba（分词/关键词）、snownlp（中文情感分析）。
"""

import re
from typing import Dict, Any, List, Optional, Tuple


class ContentAnalyzer:
    """
    基于 NLP 的内容特征分析器
    - 表层文本特征：字数、句数、段落、提及、链接、标签
    - 语言风格：情感极性、人称代词、可读性、表情符号
    - 多媒体特征
    """

    # 第一/第二人称代词集合（中文）
    FIRST_PERSON_PRONOUNS = frozenset({'我', '我们', '咱', '咱们', '本人', '俺', '鄙人', '在下'})
    SECOND_PERSON_PRONOUNS = frozenset({'你', '你们', '您', '大家', '各位', '诸位'})

    # 句子结束符
    SENTENCE_ENDINGS = frozenset({'。', '！', '？', '…', '.', '!', '?'})

    def __init__(self):
        self._jieba_available = False
        self._snownlp_available = False
        self._init_nlp_libraries()

    def _init_nlp_libraries(self):
        """尝试初始化 NLP 库，失败时静默降级"""
        try:
            import jieba
            import jieba.analyse
            self._jieba_available = True
        except ImportError:
            pass

        try:
            import snownlp
            self._snownlp_available = True
        except ImportError:
            pass

    # ------ 正则工具 -----------
    @staticmethod
    def _clean_html(text: str) -> str:
        return re.sub(r'<[^>]+>', '', text)

    @staticmethod
    def _clean_mentions(text: str) -> str:
        return re.sub(r'@[\w\u4e00-\u9fff\-]+', '', text)

    @staticmethod
    def _clean_links(text: str) -> str:
        return re.sub(r'https?://\S+', '', text)

    def clean_text(self, text: str) -> str:
        """去 HTML 标签、@提及、链接后的纯文本"""
        text = self._clean_html(text)
        text = self._clean_mentions(text)
        text = self._clean_links(text)
        return text.strip()

    @staticmethod
    def extract_mentions(text: str) -> List[str]:
        return re.findall(r'@([\w\u4e00-\u9fff\-]+)', text)

    @staticmethod
    def extract_links(text: str) -> List[str]:
        return re.findall(r'https?://\S+', text)

    @staticmethod
    def extract_hashtags(text: str) -> List[str]:
        """提取 #话题#（知乎/微博风格）"""
        return re.findall(r'#([^#]+)#', text)

    # ----- 表层文本特征 -----
    def analyze_surface_text(self, title: str, excerpt: str, text_full: str = "") -> Dict[str, Any]:
        """
        分析表层文本特征 → 对应 schema.content_features.surface_text

        :param title:     标题
        :param excerpt:   正文/摘要
        :param text_full: 完整原文（可选）
        """
        text = text_full or excerpt
        combined = f"{title}\n{excerpt}" if title else text

        mentions = self.extract_mentions(combined)
        links = self.extract_links(combined)

        # 次数(jieba 分词)
        word_count = 0
        if self._jieba_available:
            import jieba
            word_count = len(jieba.lcut(text))

        clean = self.clean_text(combined)

        return {
            "text_full": combined,  # 原始文本（包含标题）
            "text_clean": clean,  # 清理后的文本（去 HTML、@提及、链接）
            "char_count": len(text),  # 字数（包含标题）
            "word_count": word_count,  # 分词数（包含标题）
            "sentence_count": self._count_sentences(text),  # 句数（包含标题）
            "paragraph_breaks": text.count('\n'),  # 段落数（包含标题）
            "has_poll": False,  # 是否包含投票（暂不实现）
            "has_mention": len(mentions) > 0,  # 是否包含提及
            "mention_count": len(mentions),  # 提及数（包含标题）
            "has_link": len(links) > 0,  # 是否包含链接
            "link_domain": self._extract_domain(links[0]) if links else None,  # 链接域名（第一个链接）
        }

    # ----- 语言风格特征 -----

    def analyze_language_style(self, text: str) -> Dict[str, Any]:
        """
        分析语言风格 → 对应 schema.content_features.language_style

        :param text: 待分析文本（正文部分，不含标题）
        """
        sentences = [s.strip() for s in re.split(r'[。！？.!?\n]+', text) if s.strip()]
        sentence_count = len(sentences)
        char_count = len(text)
        avg_sentence_length = round(char_count / sentence_count, 2) if sentence_count else 0.0

        # 情感极性 (-1 ~ 1)
        sentiment_polarity = self._analyze_sentiment(text)

        # 人称代词
        first_p, second_p, total_words = self._count_pronouns(text)

        # 关键词（jieba TF-IDF）
        keywords = self._extract_keywords(text)

        # Emoji
        emoji_count = self._count_emojis(text)

        # 括号补充语
        has_bracket_aside = bool(re.search(r'[（(].{,30}[)）]', text))

        return {
            "avg_sentence_length": avg_sentence_length,  # 平均句长（字符数）
            "readability_score": 0.0,  # 可读性分数（暂不实现）
            "sentiment_polarity": round(sentiment_polarity, 4),  # 情感极性（-1 ~ 1）
            "sentiment_variance": 0.0,  # 情感变化（暂不实现）
            "pronoun_usage": {
                "first_person_ratio": round(first_p / max(total_words, 1), 4),  # 人称代词占比
                "second_person_ratio": round(second_p / max(total_words, 1), 4),  # 二称代词占比
            },
            "jargon_ratio": 0.0,  # 专业术语占比
            "emoji_count": emoji_count,  # Emoji 数量
            "caps_ratio": 0.0,  # 大写字母占比
            "has_bracket_aside": has_bracket_aside,  # 是否包含括号补充语
        }

    # ------ 多媒体分析 -----------
    @staticmethod
    def analyze_multimedia(platform_data: Dict[str, Any]) -> Dict[str, Any]:
        """分析多媒体特征 → 对应 schema.content_features.multimedia"""
        meta = platform_data.get("content_meta", {})
        is_video = meta.get("is_video_answer", 0)
        duration = meta.get("duration", 0)

        if is_video:
            return {
                "media_type": "视频",
                "media_count": 1,
                "image_style": None,
                "video_duration_sec": float(duration) if duration else None,
            }

        # 检查是否有图片（excerpt 含图片标签或 thumbnail 非空）
        thumbnail = meta.get("thumbnail", "")
        if thumbnail:
            return {
                "media_type": "图片",
                "media_count": 1,
                "image_style": None,
                "video_duration_sec": None,
            }
        # 也可通过 excerpt 中是否含 <img> 或 ![] 判断
        excerpt = meta.get("excerpt", "")
        if re.search(r'<img|!\[', excerpt):
            return {
                "media_type": "图片",
                "media_count": excerpt.count('<img'),
                "image_style": None,
                "video_duration_sec": None,
            }

        return {
            "media_type": "无",
            "media_count": 0,
            "image_style": None,
            "video_duration_sec": None,
        }

    # ------ 内部辅助方法 -----------
    def _count_sentences(self, text: str) -> int:
        if not text:
            return 0
        parts = re.split(r'[。！？.!?\n]+', text)
        return len([s for s in parts if s.strip()])

    def _analyze_sentiment(self, text: str) -> float:
        """情感分析，返回 -1 ~ 1"""
        if not text:
            return 0.0
        if self._snownlp_available:
            try:
                from snownlp import SnowNLP
                s = SnowNLP(text[:1000])  # 取前1000字
                return s.sentiments * 2 - 1
            except Exception:
                pass
        # 降级：简单正负词典匹配
        return self._rule_based_sentiment(text[:1000])

    def _rule_based_sentiment(self, text: str) -> float:
        """简单词典情感分析降级方案"""
        positive = {'好', '棒', '优秀', '精彩', '喜欢', '赞', '支持', '厉害', '感动', '美',
                    '开心', '幸福', '成功', '进步', '突破', '创新', '贡献'}
        negative = {'差', '烂', '垃圾', '恶心', '讨厌', '愤怒', '崩溃', '失败', '问题',
                    '危机', '担忧', '焦虑', '失望', '打击', '恶化'}
        pos_count = sum(1 for w in positive if w in text)
        neg_count = sum(1 for w in negative if w in text)
        total = pos_count + neg_count
        if total == 0:
            return 0.0
        return (pos_count - neg_count) / total

    def _count_pronouns(self, text: str) -> Tuple[float, float, float]:
        """统计人称代词使用"""
        first_p = second_p = total_words = 0
        if self._jieba_available:
            import jieba
            words = jieba.lcut(text)
            total_words = len(words)
            for w in words:
                if w in self.FIRST_PERSON_PRONOUNS:
                    first_p += 1
                elif w in self.SECOND_PERSON_PRONOUNS:
                    second_p += 1
        else:
            for w in self.FIRST_PERSON_PRONOUNS:
                first_p += text.count(w)
            for w in self.SECOND_PERSON_PRONOUNS:
                second_p += text.count(w)
            total_words = len(text)
        return float(first_p), float(second_p), float(total_words)

    def _extract_keywords(self, text: str) -> List[Tuple[str, float]]:
        """提取关键词列表 (词, 权重)"""
        if not text or not self._jieba_available:
            return []
        try:
            import jieba.analyse
            return jieba.analyse.extract_tags(text, topK=10, withWeight=True)
        except Exception:
            return []

    @staticmethod
    def _count_emojis(text: str) -> int:
        emoji_pattern = re.compile(
            "[\U0001F000-\U0001FFFF"  # 杂项符号和表情符号
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+", re.UNICODE
        )
        return sum(len(e) for e in emoji_pattern.findall(text))

    @staticmethod
    def _extract_domain(url: str) -> Optional[str]:
        m = re.match(r'https?://([^/]+)', url)
        return m.group(1) if m else None
