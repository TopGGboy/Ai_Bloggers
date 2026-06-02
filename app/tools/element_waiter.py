from playwright.async_api import Page, Locator, TimeoutError as PlaywrightTimeoutError
from typing import Optional, Literal, Union
import random

from app.tools.logging_config import LoggingConfig
from app.core.config_manager import config

# 限定condition可选值（类型提示+参数校验）
ConditionType = Literal["visible", "hidden", "attached", "detached"]


class AsyncElementWaiter:
    def __init__(self, page: Page, timeout: int = 10000):
        """
        初始化等待元素

        :param page: Playwright Page对象
        :param timeout: 等待超时时间(ms)
        """
        self.page = page
        self.timeout = timeout
        # 反风控：随机延迟配置（模拟真人操作）
        self.click_delay_range = (50, 200)  # 点击延迟50-200ms
        self.type_delay_range = (50, 150)  # 打字延迟50-150ms

        self.log = LoggingConfig(log_file_path=config.logfile_path, log_level=config.log_level).get_logger(
            self.__class__.__name__)

    async def wait_for_element(self,
                               selector: str,
                               selector_type: Literal["css", "xpath"] = "xpath",
                               condition: ConditionType = 'visible',
                               timeout: Optional[int] = None) -> Optional[Locator]:
        """
        等待元素出现（优化：支持CSS/XPath，减少冗余，参数校验）

        :param selector: 选择器（CSS/XPath）
        :param selector_type: 选择器类型（css/xpath）
        :param condition: 等待条件（枚举限定，避免传错）
        :param timeout: 超时时长(ms)
        :return: Locator 对象或 None（detached状态返回None）
        """
        # 参数校验（新增：友好提示错误）
        if timeout is None:
            timeout = self.timeout
        if timeout <= 0:
            self.log.error("超时时间必须大于0")
            return None

        try:
            # 统一创建locator（解决冗余问题）
            if selector_type == "css":
                locator = self.page.locator(selector).first
            elif selector_type == "xpath":
                locator = self.page.locator(f"xpath={selector}").first
            else:
                self.log.error(f"不支持的选择器类型：{selector_type}")
                return None

            # 统一等待逻辑（减少冗余）
            await locator.wait_for(state=condition, timeout=timeout)

            # detached状态返回None（避免误导）
            if condition == "detached":
                self.log.info(f"元素已移除DOM：{selector}")
                return None

            self.log.info(f"元素满足条件 {condition}：{selector}")
            return locator

        except PlaywrightTimeoutError:
            self.log.warning(f"等待元素超时（{condition}）：{selector}")
            return None
        # 仅捕获Playwright相关异常，避免掩盖关键错误（优化：缩小异常范围）
        except Exception as e:
            self.log.error(f"等待元素失败：{e}", exc_info=False)
            return None

    async def wait_for_locator(self, locator: Locator, condition: ConditionType = 'visible',
                               timeout: Optional[int] = None) -> Optional[Locator]:
        """
        等待 Locator 满足条件（新增：支持 Playwright 原生定位器）

        :param locator: Playwright Locator 对象
        :param condition: 等待条件
        :param timeout: 超时时间 (ms)
        :return: Locator 对象或 None
        """
        if timeout is None:
            timeout = self.timeout

        try:
            await locator.wait_for(state=condition, timeout=timeout)

            if condition == "detached":
                self.log.info(f"元素已移除 DOM")
                return None

            self.log.info(f"元素满足条件 {condition}")
            return locator

        except PlaywrightTimeoutError:
            self.log.warning(f"等待元素超时（{condition}）")
            return None
        except Exception as e:
            self.log.error(f"等待元素失败：{e}", exc_info=False)
            return None

    async def safe_click_locator(self, locator: Locator, timeout: Optional[int] = None):
        """
        安全点击 Locator（新增：直接操作 Locator 对象）

        :param locator: Playwright Locator 对象
        :param timeout: 超时时间 (ms)
        """
        try:
            target = await self.wait_for_locator(
                locator=locator,
                condition="visible",
                timeout=timeout
            )
            if not target:
                return

            await target.click(
                delay=random.randint(*self.click_delay_range),
                timeout=timeout or self.timeout
            )
            self.log.info(f"安全点击元素")

        except PlaywrightTimeoutError:
            self.log.warning(f"点击元素超时")
        except Exception as e:
            self.log.error(f"点击元素失败：{e}", exc_info=False)

    async def safe_fill_locator(self, locator: Locator, text: str, timeout: Optional[int] = None):
        """
        安全填充输入框（新增：直接操作 Locator 对象）

        :param locator: Playwright Locator 对象
        :param text: 要填充的文本
        :param timeout: 超时时间 (ms)
        """
        try:
            target = await self.wait_for_locator(
                locator=locator,
                condition="visible",
                timeout=timeout
            )
            if not target:
                return

            await target.fill(text, timeout=timeout or self.timeout)
            self.log.info(f"填充输入框：{text[:50]}...")

        except PlaywrightTimeoutError:
            self.log.warning(f"填充输入框超时")
        except Exception as e:
            self.log.error(f"填充输入框失败：{e}", exc_info=False)

    async def safe_click(self,
                         selector: str,
                         selector_type: Literal["css", "xpath"] = "xpath",
                         timeout: Optional[int] = None):
        """
        安全点击元素（优化：等待可点击，加随机延迟，反风控）
        :param selector: 选择器
        :param selector_type: 选择器类型（css/xpath）
        :param timeout:  超时时间(ms)
        """
        try:
            locator = await self.wait_for_element(
                selector=selector,
                selector_type=selector_type,
                condition="visible",
                timeout=timeout
            )
            if not locator:
                return

            # 反风控：随机延迟点击，模拟真人
            await locator.click(
                delay=random.randint(*self.click_delay_range),
                timeout=timeout or self.timeout
            )
            self.log.info(f"安全点击元素：{selector}")

        except PlaywrightTimeoutError:
            self.log.warning(f"点击元素超时：{selector}")
        except Exception as e:
            self.log.error(f"点击元素失败：{e}", exc_info=False)

    async def clear_input_field(self,
                                selector: str,
                                selector_type: Literal["css", "xpath"] = "xpath",
                                timeout: Optional[int] = None):
        """
        清空输入框内容（优化：彻底清空，适配多平台）

        Args:
            selector: 选择器
            selector_type: 选择器类型（css/xpath）
            timeout: 超时时间（毫秒）
        """
        try:
            locator = await self.wait_for_element(
                selector=selector,
                selector_type=selector_type,
                condition="visible",
                timeout=timeout
            )
            if not locator:
                return

            # 优化：先聚焦→选中全部→清空，适配知乎/小红书输入框
            await locator.focus()
            await self.page.keyboard.press("Control+A")  # 全选内容
            await self.page.keyboard.press("Backspace")  # 删除
            await locator.fill("")  # 兜底清空
            self.log.info(f"清空输入框：{selector}")

        except Exception as e:
            self.log.error(f"清空输入框失败：{e}", exc_info=False)

    async def wait_for_url_change(self,
                                  old_url: str,
                                  timeout: Optional[int] = None) -> bool:
        """
        等待 URL 变化（最终修复版：解决参数未接收+JS注入风险）

        Args:
            old_url: 原始 URL
            timeout: 超时时间（毫秒，与其他方法统一）

        Returns:
            bool: URL 是否发生变化
        """
        try:
            if timeout is None:
                timeout = self.timeout

            # 核心修复：JS函数显式接收args参数（[oldUrl]）
            await self.page.wait_for_function(
                # 箭头函数接收参数 → 避免JS注入 + 变量未定义
                "([oldUrl]) => window.location.href !== oldUrl",
                arg=[old_url],  # 传递参数到JS函数
                timeout=timeout
            )
            self.log.info(f"URL已变化，原URL：{old_url[:50]}...")
            return True
        except PlaywrightTimeoutError:
            self.log.warning(f"等待 URL 变化超时（{timeout}ms）")
            return False
        except Exception as e:
            self.log.error(f"等待 URL 变化失败：{e}", exc_info=False)
            return False

    async def get_element_text(self,
                               selector: str,
                               selector_type: Literal["css", "xpath"] = "xpath",
                               text_type: Literal["inner", "content"] = "inner",
                               timeout: Optional[int] = None) -> Optional[str]:
        """
        获取元素文本内容（优化：支持inner_text/text_content）

        Args:
            selector: 选择器
            selector_type: 选择器类型（css/xpath）
            text_type: 获取文本类型（inner: 渲染后文本，content: 原始文本）
            timeout: 超时时间（毫秒）

        Returns:
            元素文本内容或 None
        """
        try:
            locator = await self.wait_for_element(
                selector=selector,
                selector_type=selector_type,
                condition="visible",
                timeout=timeout
            )
            if not locator:
                return None

            # 优化：支持两种文本获取方式
            if text_type == "inner":
                text = locator.inner_text()
            else:
                text = locator.text_content()

            self.log.info(f"获取元素文本：{text[:50]}...")
            return text.strip() if text else None

        except Exception as e:
            self.log.error(f"获取元素文本失败：{e}", exc_info=False)
            return None

    async def type_text(self,
                        selector: str,
                        text: str,
                        selector_type: Literal["css", "xpath"] = "xpath",
                        simulate_human: bool = True,
                        timeout: Optional[int] = None):
        """
        在输入框中输入文本（优化：模拟真人打字，反风控）

        Args:
            selector: 选择器
            selector_type: 选择器类型（css/xpath）
            text: 要输入的文本
            simulate_human: 是否模拟真人打字（反风控）
            timeout: 超时时间（毫秒）
        """
        try:
            locator = await self.wait_for_element(
                selector=selector,
                selector_type=selector_type,
                condition="visible",
                timeout=timeout
            )
            if not locator:
                return

            # 反风控：模拟真人打字（逐字符输入）
            if simulate_human:
                await locator.type(
                    text,
                    delay=random.randint(*self.type_delay_range)
                )
            else:
                await locator.fill(text)  # 快速填充（测试用）

            self.log.info(f"输入文本：{text[:50]}...")

        except Exception as e:
            self.log.error(f"输入文本失败：{e}", exc_info=False)
