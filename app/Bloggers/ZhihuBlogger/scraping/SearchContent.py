import asyncio
import re
from typing import Optional, List
from bs4 import BeautifulSoup
from playwright.async_api import Page, Locator
from urllib.parse import quote

from app.core.config_manager import config
from app.tools.LoggingConfig import LoggingConfig
from app.tools.ElementWaiter import AsyncElementWaiter

num_pattern = re.compile(r'\d+')


class AsyncSearchContent:
    """
    按关键词搜索知乎内容（用于竞品洞察等场景）
    逐条处理模式：展开内容 → 爬取 → 进评论 → 爬取评论 → 退出 → 下一条
    """

    def __init__(self, page: Page):
        self.page = page
        self.waiter = AsyncElementWaiter(self.page)
        self.log = LoggingConfig(log_file_path=config.logfile_path, log_level=config.log_level).get_logger(
            f"{self.__class__.__name__}.SearchContent")

    async def search(self, query: str, max_items: int = 20, max_comments: int = 20) -> List[
        dict]:
        """
        搜索知乎内容（逐条处理模式）
        :param query: 搜索关键词
        :param max_items: 最大处理条数（默认 20）
        :param max_comments: 最大评论条数（默认 20）
        :return: 搜索结果列表
        """
        try:
            if max_items <= 0:
                return []

            query = quote(query, safe="")
            # 1. 进入搜索主页
            await self.page.goto(f'https://www.zhihu.com/search?type=content&q={query}')

            # 2. 等待搜索结果容器加载
            await self.waiter.wait_for_element('div.SearchMain', selector_type="css")

            # 3. 滚动到底部触发懒加载
            for _ in range(2):
                await self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await asyncio.sleep(2)

            # 4. 滚动回到顶部，准备逐条处理
            await self.page.evaluate('window.scrollTo(0, 0)')
            await asyncio.sleep(1)

            cards_locator = self.page.locator(
                'div.SearchMain div.ListShortcut div[role="list"] div[role="listitem"].SearchResult-Card:not(.AnswerItem-hotLanding)'
            )
            card_count = await cards_locator.count()

            self.log.info(f"共找到 {card_count} 条搜索结果，开始逐条处理（最多 {max_items} 条）")

            # 6. 逐条处理
            results = []
            for i in range(min(card_count, max_items)):
                self.log.info(f"开始处理第 {i + 1} 条")
                card = cards_locator.nth(i)
                await card.scroll_into_view_if_needed()
                await asyncio.sleep(0.5)

                item_data = await self._process_single_item(card, i + 1, max_comments)
                if item_data:
                    results.append(item_data)

            self.log.info(f"✅ 搜索「{query}」完成，共获取 {len(results)} 条结果")
            return results

        except Exception as e:
            self.log.error(f"搜索知乎内容失败：{e}")
            return []

    async def _process_single_item(self, card: Locator, index: int, max_comments: int = 20) -> Optional[dict]:
        """
        处理单条搜索结果（基于卡片 Locator 精准操作）
        :param card: 当前卡片的 Locator
        :param index: 索引（用于日志）
        :param max_comments: 最大评论条数（默认 20）
        :return: 完整的数据字典
        """
        try:
            # 1. 展开阅读全文
            expanded = await self._expand_current_item(card)
            if not expanded:
                return None
            # # 2. 爬取文章基本信息
            content_data = await self._parse_current_content(card)

            comments_data = None
            if max_comments > 0:
                # 3. 点击评论，进入评论区
                await self._enter_comments(card)
                # 4. 爬取评论数据
                comments_data = await self._parse_comments(max_comments)
                # 5. 退出评论区（关闭弹窗或返回）
                await self._exit_comments()

            # 6. 组装数据
            result = {
                **content_data,
                "comments": comments_data
            }
            self.log.info(f"第 {index} 条处理完成：{content_data.get('title', '未知标题')}")
            return result
        except Exception as e:
            self.log.error(f"处理第 {index} 条结果失败：{e}")
            return None

    # ==================== 阶段 1：展开阅读全文 ====================

    async def _expand_current_item(self, card: Locator):
        """
        展开当前卡片结果的"阅读全文"按钮
        :param card: 当前卡片的 Locator
        :return: 是否成功展开
        """
        try:
            read_more_btn = card.locator('button.ContentItem-more')
            if await read_more_btn.count() > 0:
                await read_more_btn.first.scroll_into_view_if_needed()
                await asyncio.sleep(0.3)
                await read_more_btn.first.click()
                await asyncio.sleep(1)
                self.log.info("✅ 已展开阅读全文")
                return True
            else:
                self.log.info("当前结果无需展开")
                return False
        except Exception as e:
            self.log.warning(f"展开阅读全文失败：{e}")

    async def _parse_current_content(self, card: Locator) -> dict:
        """
        爬取当前结果的基本信息（精准获取单条搜索卡片 outerHTML）
        :param card: 当前卡片的 Locator
        :return: {title, link, content, author_name, author_link, agree_num, comment_num, edit_time}
        """
        try:
            # 精准获取当前卡片的 outerHTML（不拉取整个页面）
            card_html = await card.evaluate('el => el.outerHTML')
            soup = BeautifulSoup(card_html, 'html.parser')

            # 1.标题与链接
            title_tag = soup.find("h2", class_="ContentItem-title")
            title = title_tag.get_text(strip=True) if title_tag else ""
            link = ""
            if title_tag:
                a_tag = title_tag.find("a")
                if a_tag and a_tag.get("href"):
                    href = a_tag.get("href")
                    link = f"https://www.zhihu.com{href}" if href.startswith("/") else f"https:{href}"

            # 2. 内容摘要
            content_tag = soup.find("span", class_=["RichText", "ztext", "CopyrightRichText-richText"])
            content = content_tag.get_text(strip=True, separator="\n") if content_tag else ""

            # 3. 作者名称 + 作者链接
            author_name = ""
            author_link = ""
            author_name_meta = soup.find("meta", itemprop="name")
            if author_name_meta:
                author_name = author_name_meta.get("content", "")

            author_link_meta = soup.find("meta", itemprop="url")
            if author_link_meta:
                author_link = author_link_meta.get("content", "")
                # 补全协议
                if author_link.startswith("//"):
                    author_link = f"https:{author_link}"

            # 4. 赞同数
            agree_num = 0
            agree_btn = soup.find("button", class_="VoteButton--up")
            if agree_btn:
                agree_text = agree_btn.get_text(strip=True)
                agree_match = re.search(r"(\d+)", agree_text)
                if agree_match:
                    agree_num = int(agree_match.group())

            # 5. 评论数（修复版：用固定class定位，兼容嵌套标签）
            comment_num = 0
            # 精准匹配知乎评论按钮的核心class，无视动态css类
            comment_btn = soup.find("button", class_=lambda
                x: x and "ContentItem-action" in x and "Button--plain" in x and "条评论" not in x)
            if comment_btn:
                comment_text = comment_btn.get_text(strip=True)
                # 正则提取所有数字，兼容各种格式
                comment_match = re.search(r'\d+', comment_text)
                if comment_match:
                    comment_num = int(comment_match.group())

            # 6. 发布/编辑时间（清洗掉"发布于"文字）
            edit_time = ""
            time_div = soup.find("div", class_="ContentItem-time")
            if time_div:
                time_a = time_div.find("a")
                if time_a:
                    time_text = time_a.get_text(strip=True)
                    edit_time = time_text.replace("发布于", "").strip()

            return {
                "title": title,
                "link": link,
                "content": content,
                "author_name": author_name,
                "author_link": author_link,
                "agree_num": agree_num,
                "comment_num": comment_num,
                "edit_time": edit_time
            }
        except Exception as e:
            self.log.error(f"解析内容失败：{e}")
            return {}

    # ==================== 阶段 2：进入评论区 ====================

    async def _enter_comments(self, card: Locator):
        """
        在当前卡片内点击评论按钮，进入评论区
        :param card: 当前卡片的 Locator
        """
        try:
            comment_btn = card.locator('button:has-text("条评论")')
            if await comment_btn.count() > 0:
                await comment_btn.first.scroll_into_view_if_needed()
                await comment_btn.first.click()
                await asyncio.sleep(2)
                self.log.info("✅ 已进入评论区")
            else:
                self.log.warning("未找到评论按钮")
        except Exception as e:
            self.log.warning(f"进入评论区失败：{e}")

    async def _parse_comments(self, max_comments: int = 20) -> List[dict]:
        """
        爬取评论数据（精准解析评论区弹窗 HTML）
        :return: 评论列表 [{comment_id, author, author_link, author_avatar, content, time, location, tag, like_count, reply_count}, ...]
        """
        try:
            # 精准定位评论区弹窗容器（不拉取整个页面）
            modal = self.page.locator('.Modal-content, .PolarisModal-content, [role="dialog"]').first
            if await modal.count() == 0:
                self.log.info("未找到评论区弹窗容器")
                return []

            modal_html = await modal.evaluate('el => el.outerHTML')
            soup = BeautifulSoup(modal_html, 'html.parser')

            # 每条评论是一个带 data-id 属性的 div
            comment_items = soup.find_all('div', attrs={'data-id': True})

            comments = []
            for item in comment_items:
                try:
                    comment_id = item.get('data-id', '')

                    # ====== 作者信息 ======
                    author_name = ''
                    author_link = ''
                    for a in item.find_all('a', href=True):
                        href = a.get('href', '')
                        if '/people/' in href and not a.find('img'):
                            author_name = a.get_text(strip=True)
                            author_link = href if href.startswith('http') else f"https://www.zhihu.com{href}"
                            break

                    # 作者头像
                    author_avatar = ''
                    avatar_img = item.find('img', class_='Avatar')
                    if avatar_img:
                        author_avatar = avatar_img.get('src', '')

                    # ====== 评论内容 ======
                    content_div = item.find('div', class_='CommentContent')
                    content = content_div.get_text(strip=True, separator='\n') if content_div else ''

                    # ====== 时间 / 地区 / 标签 ======
                    time = ''
                    location = ''
                    tag = ''
                    for span in item.find_all('span'):
                        text = span.get_text(strip=True)
                        if not text or text == '·':
                            continue
                        # 日期
                        if re.match(r'^\d{4}-\d{2}-\d{2}$', text):
                            time = text
                        # 地区 / 标签（知乎使用 href="" 标记这类 span）
                        elif span.get('href') is not None and span.get('href') == '':
                            if text in ('热评', '置顶', '推荐', '精选'):
                                tag = text
                            else:
                                location = text

                    # ====== 点赞数 ======
                    like_count = 0
                    like_svg = item.find('svg', class_=lambda c: c and 'HeartFill24' in c)
                    if like_svg:
                        like_btn = like_svg.find_parent('button')
                        if like_btn:
                            like_text = like_btn.get_text(strip=True)
                            like_match = num_pattern.search(like_text)
                            if like_match:
                                like_count = int(like_match.group())

                    # ====== 回复数 ======
                    reply_count = 0
                    reply_btn = item.find('button', string=re.compile(r'查看全部'))
                    if reply_btn:
                        reply_text = reply_btn.get_text(strip=True)
                        reply_match = num_pattern.search(reply_text)
                        if reply_match:
                            reply_count = int(reply_match.group())

                    if content:
                        comments.append({
                            "comment_id": comment_id,
                            "author": author_name,
                            "author_link": author_link,
                            "author_avatar": author_avatar,
                            "content": content,
                            "time": time,
                            "location": location,
                            "tag": tag,
                            "like_count": like_count,
                            "reply_count": reply_count,
                        })

                except Exception as e:
                    self.log.warning(f"解析单条评论失败：{e}")
                    continue

            self.log.info(f"共获取 {len(comments)} 条评论")
            return comments

        except Exception as e:
            self.log.error(f"解析评论失败：{e}")
            return []

    async def _exit_comments(self):
        """退出评论区（关闭弹窗或返回）"""
        try:
            await self.page.keyboard.press('Escape')
            await asyncio.sleep(1)
            self.log.info("✅ 已退出评论区")
        except Exception as e:
            self.log.warning(f"退出评论区失败：{e}")

    # ==================== 辅助方法 ====================

    async def _parse_html(self, html_data: str) -> List[dict]:
        """
        解析知乎搜索结果 HTML（保留旧逻辑，兼容备用）
        :param html_data: 知乎搜索结果 HTML 内容
        :return: 搜索结果列表
        """
        soup = BeautifulSoup(html_data, 'html.parser')

        search_main = soup.find("div", class_="SearchMain")
        if not search_main:
            self.log.warning("未找到 SearchMain 容器")
            return []

        list_shortcut = search_main.find("div", class_="ListShortcut")
        if not list_shortcut:
            self.log.warning("未找到 ListShortcut 容器")
            return []

        list_container = list_shortcut.find("div", class_="css-0", role="list")
        if not list_container:
            self.log.warning("未找到列表容器（role=list）")
            return []

        results = []
        for item in list_container.find_all("div", role="listitem"):
            if "SearchResult-Card" not in item.get("class", []):
                continue

            try:
                title_tag = item.find("h2", class_="ContentItem-title")
                title = title_tag.get_text(strip=True) if title_tag else ""
                link = ""
                if title_tag:
                    a_tag = title_tag.find("a")
                    if a_tag and a_tag.get("href"):
                        href = a_tag.get("href")
                        link = f"https://www.zhihu.com{href}" if href.startswith("/") else f"https:{href}"

                content_tag = item.find("span", class_="RichText ztext CopyrightRichText-richText")
                content = content_tag.get_text(strip=True, separator="\n") if content_tag else ""

                if title or link:
                    results.append({"title": title, "link": link, "content": content})
            except Exception as e:
                self.log.warning(f"解析单条结果失败：{e}")
                continue

        return results


async def test_zhihu_search_fetcher():
    from app.core.PlaywrightDriver import AsyncPlaywrightDriver

    USER_DATA_DIR = r"D:\pythonproject\Ai_Blogger\driver\playwright_data"

    async with AsyncPlaywrightDriver(base_data_dir=USER_DATA_DIR) as driver:
        browser, context, page = await driver.launch_browser(
            viewport_type="pc",
            user_data_dir=f"{USER_DATA_DIR}/zhihu_data"
        )

        search_content = AsyncSearchContent(page)

        results = await search_content.search("雷军", max_items=5)
        for i, item in enumerate(results, 1):
            print(f"\n=== 第 {i} 条 ===")
            print(f"标题：{item.get('title')}")
            print(f"内容：{item.get('content', '')[:100]}...")
            print(f"评论数：{len(item.get('comments', []))}")


if __name__ == '__main__':
    asyncio.run(test_zhihu_search_fetcher())
