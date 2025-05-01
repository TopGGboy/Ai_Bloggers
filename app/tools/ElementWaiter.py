import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from selenium.webdriver.common.keys import Keys


class ElementWaiter:
    def __init__(self, driver, default_timeout=10, poll_frequency=0.5, ignored_exceptions=None):
        """
        初始化等待工具类
        :param driver: WebDriver实例
        :param default_timeout: 默认超时时间（秒）
        :param poll_frequency: 轮询间隔（秒）
        :param ignored_exceptions: 忽略的异常列表（如[TimeoutException]）
        """
        self.driver = driver
        self.default_timeout = default_timeout
        self.poll_frequency = poll_frequency
        self.ignored_exceptions = ignored_exceptions or [TimeoutException, StaleElementReferenceException]

    def wait_for_element(self, by, value, condition="presence", timeout=None, custom_message=None):
        """
        通用等待方法，支持多种条件
        :param by: 定位方式（如By.ID）
        :param value: 定位值
        :param condition: 等待条件（presence/visibility/clickable/text）
        :param timeout: 覆盖默认超时时间
        :param custom_message: 自定义日志消息
        :return: WebElement 或 None
        """
        conditions = {
            "presence": EC.presence_of_element_located,
            "visibility": EC.visibility_of_element_located,
            "clickable": EC.element_to_be_clickable,
            "text": EC.text_to_be_present_in_element
        }
        timeout = timeout or self.default_timeout
        locator = (by, value)
        try:
            element = WebDriverWait(
                self.driver,
                timeout,
                poll_frequency=self.poll_frequency,
                ignored_exceptions=self.ignored_exceptions
            ).until(conditions[condition](locator))

            logging.info(f"元素已找到：定位方式={by}, 值={value}, 条件={condition}")
            print(f"元素已找到：定位方式={by}, 值={value}, 条件={condition}")
            return element
        except TimeoutException as e:
            message = custom_message or f"等待元素超时：定位方式={by}, 值={value}, 条件={condition}"
            logging.error(message)
            return None  # 或抛出异常，根据需求调整
        except KeyError:
            raise ValueError(f"不支持的等待条件：{condition}")

    def wait_for_custom_condition(self, condition_func, timeout=None, *args):
        """
        自定义等待条件（支持Lambda或函数）
        :param condition_func: 返回布尔值的函数
        :param timeout: 超时时间
        :return: 函数返回值或 None
        """
        timeout = timeout or self.default_timeout
        try:
            return WebDriverWait(
                self.driver,
                timeout,
                poll_frequency=self.poll_frequency,
                ignored_exceptions=self.ignored_exceptions
            ).until(condition_func(*args))
        except TimeoutException:
            logging.error("自定义条件等待超时")
            return None

    def wait_for_url_change(self, current_url, timeout=None, custom_message=None):
        """
        等待URL发生变化
        :param current_url: 当前URL
        :param timeout: 覆盖默认超时时间
        :param custom_message: 自定义日志消息
        :return: True: 改变了 False: 未改变
        """
        timeout = timeout or self.default_timeout
        try:
            WebDriverWait(
                self.driver,
                timeout,
                poll_frequency=self.poll_frequency,
                ignored_exceptions=self.ignored_exceptions
            ).until(EC.url_changes(current_url))

            logging.info(f"URL 已发生变化：从 {current_url}")
            print(f"URL 已发生变化：从 {current_url}")
            return True
        except TimeoutException as e:
            message = custom_message or f"等待URL变化超时：当前URL={current_url}"
            logging.error(message)
            return False
        except Exception as e:
            logging.error(f"等待URL变化时发生错误：{e}")
            return False

    def safe_click(self, by, value, retries=3):
        """
        带有重试机制的点击方法。该方法会尝试点击指定的元素，如果点击失败（例如元素过期），则会重试指定的次数。

        :param by: 定位元素的方式，例如 By.ID, By.XPATH 等。
        :param value: 定位元素的值，与 by 参数一起使用。
        :param retries: 尝试点击的最大次数，默认为 3 次。
        :return: 如果成功点击元素，则返回该元素；如果所有重试都失败，则返回 False。
        """
        for attempt in range(retries):
            element = self.wait_for_element(by, value, condition="clickable")
            if element:
                try:
                    element.click()
                    logging.info(f"点击成功：第{attempt + 1}次尝试")
                    print(f"点击成功：第{attempt + 1}次尝试")
                    return element
                except StaleElementReferenceException:
                    logging.warning(f"元素已过期，正在重试：第{attempt + 1}次")
        return False

    def clear_input_field(self, by, value, timeout=None):
        """
        清空输入框内容
        :param by: 定位方式（如By.ID）
        :param value: 定位值
        :param timeout: 覆盖默认超时时间
        :return: 成功返回True，失败返回False
        """
        element = self.wait_for_element(by, value, condition="clickable", timeout=timeout)
        if element:
            try:
                element.click()
                element.send_keys(Keys.CONTROL + "a")
                element.send_keys(Keys.DELETE)
                logging.info(f"输入框已清空：定位方式={by}, 值={value}")
                print(f"输入框已清空：定位方式={by}, 值={value}")
                return True
            except Exception as e:
                logging.error(f"清空输入框时发生错误：{e}")
                return False
        else:
            logging.warning(f"无法找到元素进行清空操作：定位方式={by}, 值={value}")
            return False

    @staticmethod
    def set_implicit_wait(driver, timeout=10):
        """设置隐式等待（全局生效）"""
        driver.implicitly_wait(timeout)
        logging.info(f"隐式等待已设置为 {timeout} 秒")
