import asyncio
import logging
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
import json
from datetime import datetime
from enum import Enum, auto

from app.core.PlaywrightDriver import AsyncPlaywrightDriver
from app.Bloggers.BasePlatform import BasePlatform
from app.tools.LoggingConfig import LoggingConfig
from app.core.config_manager import config

# ==================== 常量定义 ====================
DEFAULT_MONITOR_INTERVAL = 600  # 默认监控间隔（秒）
DEFAULT_MONITOR_TIMEOUT = 600  # 默认监控任务超时（秒）
DEFAULT_PUBLISH_TIMEOUT = 300  # 默认发布超时（秒）
DEFAULT_MAX_RETRIES = 2  # 默认最大重试次数
DEFAULT_SLEEP_MIN = 2  # 默认随机睡眠最小值（秒）
DEFAULT_SLEEP_MAX = 5  # 默认随机睡眠最大值（秒）

# ==================== 常量定义 ====================
# 平台运行模式常量
PLATFORM_MODE_MONITOR_ONLY = "monitor_only"  # 只监控
PLATFORM_MODE_PUBLISH_ONLY = "publish_only"  # 只发布
PLATFORM_MODE_MONITOR_AND_PUBLISH = "monitor_and_publish"  # 监控并发布


# ==================== 数据类 ====================
class PlatformInfo:
    """平台信息封装"""

    def __init__(self, name: str, instance: BasePlatform, mode: str = PLATFORM_MODE_MONITOR_AND_PUBLISH):
        self.name = name
        self.instance = instance
        self.mode = mode
        self.registered_at = datetime.now()
        self.last_activity = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'mode': self.mode,
            'registered_at': self.registered_at.isoformat(),
            'last_activity': self.last_activity.isoformat()
        }


class TaskStats:
    """任务统计信息"""

    def __init__(self):
        self.total_tasks = 0
        self.success_tasks = 0
        self.failed_tasks = 0
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None

    def reset(self):
        self.__init__()

    def to_dict(self) -> Dict[str, Any]:
        duration = None
        if self.start_time and self.end_time:
            duration = str(self.end_time - self.start_time)

        success_rate = 0.0
        if self.total_tasks > 0:
            success_rate = (self.success_tasks / self.total_tasks) * 100

        return {
            'total_tasks': self.total_tasks,
            'success_tasks': self.success_tasks,
            'failed_tasks': self.failed_tasks,
            'duration': duration,
            'success_rate': f"{success_rate:.2f}%"
        }


# ==================== 主管理类 ====================
class MultiPlatformManager:
    """
    多平台并发管理器 v2.0

    核心功能:
    1. 单 Browser + 多 Context 架构（资源高效利用）
    2. 统一管理所有平台的生命周期
    3. 并发执行任务，故障隔离
    4. 支持动态添加/移除平台
    5. 任务队列和重试机制
    6. 状态监控和统计
    7. 分离监控任务和发布任务
    8. 支持多种运行模式（只监控、只发布、监控 + 发布）

    使用示例:
        # 创建管理器
        manager = MultiPlatformManager(md_path='./Md', base_driver_path='./driver')
        await manager.init()

        # 注册知乎平台（监控并发布模式）
        await manager.register_platform(
            platform_name='zhihu',
            platform_class=ZhihuAsyncControl,
            user_data_dir='zhihu_data',
            mode=PlatformMode.MONITOR_AND_PUBLISH
        )

        # 启动监控
        await manager.start_monitor('zhihu', interval=600)

        # 发布内容
        await manager.publish_to_platform('zhihu', content)
    """

    def __init__(self, md_path: str, base_driver_path: str):
        """
        初始化多平台管理器

        Args:
            md_path: Markdown 文件存储路径
            base_driver_path: Playwright 浏览器数据根目录
        """
        self.md_path: str = md_path
        self.base_driver_path: Path = Path(base_driver_path)
        self.driver: Optional[AsyncPlaywrightDriver] = None
        self.browser = None  # type: ignore

        # 平台管理（使用 PlatformInfo 封装）
        self.platforms: Dict[str, PlatformInfo] = {}

        # 日志
        self.log = LoggingConfig(log_file_path=config.logfile_path, log_level=config.log_level).get_logger(
            self.__class__.__name__)

        # 任务统计（使用 TaskStats 封装）
        self.task_stats = TaskStats()

        # 平台配置缓存
        self.platform_configs: Dict[str, Dict[str, Any]] = {}

        # 监控任务管理
        self.monitor_tasks: Dict[str, asyncio.Task] = {}
        self.running_monitors: Dict[str, bool] = {}

        # 回调函数注册表
        self.callbacks: Dict[str, List[Callable]] = {
            'platform_registered': [],
            'platform_unregistered': [],
            'monitor_started': [],
            'monitor_stopped': [],
            'publish_completed': []
        }

    async def init(self) -> None:
        """
        初始化多平台管理器

        1. 记录任务开始时间
        2. 确保基础目录存在
        3. 启动浏览器实例

        Raises:
            Exception: 初始化失败时抛出异常
        """
        try:
            self.task_stats.start_time = datetime.now()

            # 确保基础目录存在
            self.base_driver_path.mkdir(parents=True, exist_ok=True)

            # 启动浏览器（普通模式，不带持久化）
            self.driver = AsyncPlaywrightDriver(base_data_dir=str(self.base_driver_path))
            self.browser, _, _ = await self.driver.launch_browser()
            self.log.info("✅ 浏览器实例启动成功")

            # 触发回调
            await self._trigger_callback('platform_registered', None)

        except Exception as e:
            self.log.error(f"初始化浏览器失败：{e}", exc_info=True)
            raise

    async def register_platform(self,
                                platform_name: str,
                                platform_class: type[BasePlatform],
                                user_data_dir: str,
                                viewport_type: str = "pc",
                                custom_ua: Optional[str] = None,
                                mode: str = PLATFORM_MODE_MONITOR_AND_PUBLISH,
                                save_config: bool = True,
                                **kwargs: Any) -> None:
        """
        注册平台

        Args:
            platform_name: 平台名称
            platform_class: 平台类
            user_data_dir: 相对于 base_driver_path 的平台数据目录
            viewport_type: 视图类型
            custom_ua: 自定义 UA
            mode: 运行模式
            save_config: 是否保存配置
        """
        try:
            # 构建完整的平台数据目录路径（绝对路径）
            platform_data_path = self.base_driver_path / user_data_dir
            platform_data_path.mkdir(parents=True, exist_ok=True)

            # 为平台创建独立的持久化 Context
            context = await self.driver.create_platform_context(
                platform_name=platform_name,
                user_data_dir=str(platform_data_path),
                viewport_type=viewport_type,
                custom_ua=custom_ua
            )

            # 传入运行模式
            platform_instance = platform_class(context=context, md_path=self.md_path, mode=mode,
                                               user_data_dir=str(platform_data_path))

            # 使用 PlatformInfo 包装
            self.platforms[platform_name] = PlatformInfo(
                name=platform_name,
                instance=platform_instance,
                mode=mode
            )

            if save_config:
                self.platform_configs[platform_name] = {
                    'class_name': platform_class.__name__,
                    'user_data_dir': user_data_dir,
                    'viewport_type': viewport_type,
                    'custom_ua': custom_ua,
                    'kwargs': kwargs,
                    'registered_at': datetime.now().isoformat()
                }

            self.log.info(f"✅ 平台 {platform_name} 注册成功")

            # 触发回调
            await self._trigger_callback('platform_registered', platform_name)

        except Exception as e:
            self.log.error(f"注册平台 {platform_name} 失败：{e}", exc_info=True)
            raise

    async def unregister_platform(self, platform_name: str) -> bool:
        """移除平台"""
        if platform_name not in self.platforms:
            self.log.warning(f"平台 {platform_name} 不存在")
            return False

        try:
            # 先停止监控任务
            await self.stop_monitor(platform_name)

            platform_info = self.platforms[platform_name]
            await platform_info.instance.close()
            del self.platforms[platform_name]

            if platform_name in self.platform_configs:
                del self.platform_configs[platform_name]

            self.log.info(f"✅ 平台 {platform_name} 已移除")

            # 触发回调
            await self._trigger_callback('platform_unregistered', platform_name)
            return True

        except Exception as e:
            self.log.error(f"移除平台 {platform_name} 失败：{e}", exc_info=True)
            return False

    async def publish_to_all(self, content: Dict[str, Any], timeout: int = DEFAULT_PUBLISH_TIMEOUT) -> Dict[str, bool]:
        """并发发布到所有平台"""
        results = {}

        if not self.platforms:
            self.log.warning("没有已注册的平台")
            return results

        # 过滤出支持发布的平台
        publishable_platforms = {
            name: info for name, info in self.platforms.items()
            if info.mode in (PLATFORM_MODE_PUBLISH_ONLY, PLATFORM_MODE_MONITOR_AND_PUBLISH)
        }

        if not publishable_platforms:
            self.log.warning("没有支持发布的平台")
            return results

        self.task_stats.total_tasks += len(publishable_platforms)
        self.log.info(f"🚀 开始并发发布到 {len(publishable_platforms)} 个平台...")

        tasks = {
            name: self._publish_with_retry(info.instance, content)
            for name, platform in self.platforms.items()
        }

        try:
            completed_tasks = await asyncio.wait_for(
                asyncio.gather(*tasks.values(), return_exceptions=True),
                timeout=timeout
            )

            for (name, _), result in zip(tasks.items(), completed_tasks):
                if isinstance(result, Exception):
                    results[name] = False
                    self.task_stats.failed_tasks += 1
                    self.log.error(f"❌ 平台 {name} 发布失败：{result}")
                else:
                    results[name] = result
                    if result:
                        self.task_stats.success_tasks += 1
                    else:
                        self.task_stats.failed_tasks += 1

                    status = "✅" if result else "❌"
                    self.log.info(f"{status} 平台 {name} 发布{'成功' if result else '失败'}")

        except asyncio.TimeoutError:
            self.log.error(f"发布超时（{timeout}秒）")
            for name in self.platforms.keys():
                results[name] = False
                self.task_stats['failed_tasks'] += 1

        finally:
            # 触发回调
            await self._trigger_callback('publish_completed', results)

        return results

    async def publish_to_platform(self, platform_name: str, content: Dict[str, Any],
                                  max_retries: int = DEFAULT_MAX_RETRIES) -> bool:
        """发布到指定平台"""
        if platform_name not in self.platforms:
            self.log.error(f"平台 {platform_name} 未注册")
            return False

        platform_info = self.platforms[platform_name]

        # 检查平台模式
        if platform_info.mode == PLATFORM_MODE_MONITOR_ONLY:
            self.log.error(f"平台 {platform_name} 处于只监控模式，不支持发布")
            return False

        platform = platform_info.instance
        self.task_stats.total_tasks += 1

        success = await self._publish_with_retry(platform, content, max_retries)

        if success:
            self.task_stats.success_tasks += 1
        else:
            self.task_stats.failed_tasks += 1

        return success

    async def _publish_with_retry(self, platform: BasePlatform, content: Dict[str, Any],
                                  max_retries: int = DEFAULT_MAX_RETRIES, url: Optional[str] = None) -> bool:
        """带重试机制的发布方法"""
        for attempt in range(max_retries):
            try:
                success = await platform.publish_content(content, url)
                if success:
                    return True

            except Exception as e:
                self.log.warning(f"发布失败（第{attempt + 1}次尝试）: {e}")
                if attempt < max_retries - 1:
                    await platform.random_sleep(DEFAULT_SLEEP_MIN, DEFAULT_SLEEP_MAX)

        return False

    async def start_monitor(self, platform_name: str, interval: int = DEFAULT_MONITOR_INTERVAL,
                            hot_titles_file: Optional[str] = None) -> bool:
        """启动指定平台的监控任务"""
        if platform_name not in self.platforms:
            self.log.error(f"平台 {platform_name} 未注册")
            return False

        platform_info = self.platforms[platform_name]

        # 检查平台模式
        if platform_info.mode == PLATFORM_MODE_PUBLISH_ONLY:
            self.log.error(f"平台 {platform_name} 处于只发布模式，不支持监控")
            return False

        if platform_name in self.monitor_tasks and not self.monitor_tasks[platform_name].done():
            self.log.warning(f"平台 {platform_name} 的监控任务已在运行")
            return False

        platform = platform_info.instance

        if not hasattr(platform, 'run_monitor'):
            self.log.error(f"平台 {platform_name} 不支持监控功能")
            return False

        try:
            self.running_monitors[platform_name] = True
            task = asyncio.create_task(self._monitor_loop(platform_name, platform, interval))
            self.monitor_tasks[platform_name] = task

            self.log.info(f"✅ 平台 {platform_name} 监控任务已启动（间隔：{interval}秒）")

            # 触发回调
            await self._trigger_callback('monitor_started', platform_name)
            return True

        except Exception as e:
            self.log.error(f"启动监控任务失败：{e}", exc_info=True)
            self.running_monitors[platform_name] = False
            return False

    async def _monitor_loop(self, platform_name: str, platform: BasePlatform, interval: int) -> None:
        """监控任务循环"""
        count = 0
        while self.running_monitors.get(platform_name, False):
            count += 1
            self.log.info(f"[{platform_name}] 🔍 第 {count} 次检测")

            try:
                start_time = datetime.now()

                # 【关键修改】调用平台的 run() 方法，让它根据模式自行处理
                # 注意：run() 方法内部会自己循环，所以这里不需要 while 循环
                await platform.run(check_interval=interval)

                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                self.log.debug(f"[{platform_name}] run_monitor() 执行完成，耗时 {duration:.2f}秒")

            except asyncio.TimeoutError:
                self.log.warning(f"[{platform_name}] run_monitor() 执行超时（>{DEFAULT_MONITOR_TIMEOUT} 秒），已强制中断")

            except Exception as e:
                self.log.error(f"[{platform_name}] 监控任务失败：{e}", exc_info=True)

            # 【关键修改】run() 方法内部已经处理了 interval，不需要再 sleep
            # 但如果 run() 退出，说明收到停止信号，直接退出循环
            if not self.running_monitors.get(platform_name, False):
                self.log.info(f"[{platform_name}] 收到停止信号，退出循环")
                break

    async def stop_monitor(self, platform_name: str) -> bool:
        """停止指定平台的监控任务"""
        if platform_name not in self.monitor_tasks:
            self.log.warning(f"平台 {platform_name} 没有运行的监控任务")
            return False

        try:
            # 设置停止标志
            self.running_monitors[platform_name] = False

            # 获取任务并取消
            task = self.monitor_tasks[platform_name]
            if not task.done():
                task.cancel()
                try:
                    # 等待任务结束，最多等待 5 秒
                    await asyncio.wait_for(task, timeout=5.0)
                except asyncio.CancelledError:
                    pass
                except asyncio.TimeoutError:
                    self.log.warning(f"等待监控任务 {platform_name} 结束超时")
                except Exception as e:
                    self.log.error(f"等待监控任务结束失败：{e}", exc_info=True)

            # 清理任务和状态
            if platform_name in self.monitor_tasks:
                del self.monitor_tasks[platform_name]
            if platform_name in self.running_monitors:
                del self.running_monitors[platform_name]

            self.log.info(f"✅ 平台 {platform_name} 监控任务已停止")

            # 触发回调
            await self._trigger_callback('monitor_stopped', platform_name)
            return True

        except Exception as e:
            self.log.error(f"停止监控任务失败：{e}", exc_info=True)
            # 确保状态被清理
            if platform_name in self.monitor_tasks:
                try:
                    del self.monitor_tasks[platform_name]
                except:
                    pass
            if platform_name in self.running_monitors:
                try:
                    del self.running_monitors[platform_name]
                except:
                    pass
            return False

    async def start_all_monitors(self, intervals: Dict[str, int]) -> Dict[str, bool]:
        """启动所有平台的监控任务"""
        results = {}
        for platform_name, interval in intervals.items():
            results[platform_name] = await self.start_monitor(platform_name, interval)
        return results

    async def stop_all_monitors(self) -> Dict[str, bool]:
        """停止所有平台的监控任务"""
        results = {}
        for platform_name in list(self.monitor_tasks.keys()):
            results[platform_name] = await self.stop_monitor(platform_name)
        return results

    def get_monitor_status(self, platform_name: str) -> bool:
        """获取指定平台监控任务状态"""
        if platform_name not in self.monitor_tasks:
            return False
        task = self.monitor_tasks[platform_name]
        return not task.done()

    def list_running_monitors(self) -> List[str]:
        """列出所有正在运行的监控任务"""
        return [
            name for name, task in self.monitor_tasks.items()
            if not task.done()
        ]

    # ==================== 新增：状态查询方法 ====================
    def get_platform_info(self, platform_name: str) -> Optional[Dict[str, Any]]:
        """获取平台详细信息"""
        if platform_name not in self.platforms:
            return None
        return self.platforms[platform_name].to_dict()

    def get_all_platforms_info(self) -> List[Dict[str, Any]]:
        """获取所有平台的信息"""
        return [info.to_dict() for info in self.platforms.values()]

    def get_resource_stats(self) -> Dict[str, Any]:
        """获取资源使用统计"""
        total_pages = 0
        for info in self.platforms.values():
            platform = info.instance
            if hasattr(platform, 'monitor_page') and platform.monitor_page:
                total_pages += 1
            if hasattr(platform, 'publish_page') and platform.publish_page:
                total_pages += 1

        return {
            'platform_count': len(self.platforms),
            'active_monitors': len(self.running_monitors),
            'total_pages': total_pages,
            'task_stats': self.task_stats.to_dict()
        }

    def register_callback(self, event: str, callback: Callable) -> None:
        """
        注册回调函数

        支持的事件:
        - platform_registered: 平台注册成功
        - platform_unregistered: 平台移除成功
        - monitor_started: 监控任务启动
        - monitor_stopped: 监控任务停止
        - publish_completed: 发布完成

        Args:
            event: 事件名称
            callback: 回调函数
        """
        if event in self.callbacks:
            self.callbacks[event].append(callback)
            self.log.info(f"✅ 回调函数已注册：{event}")

    async def _trigger_callback(self, event: str, data: Any) -> None:
        """触发回调函数"""
        if event in self.callbacks:
            for callback in self.callbacks[event]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(data)
                    else:
                        callback(data)
                except Exception as e:
                    self.log.error(f"回调函数执行失败 ({event}): {e}")

    async def close_all(self) -> None:
        """关闭所有平台和资源"""
        self.log.info("正在关闭所有平台...")
        self.task_stats.end_time = datetime.now()

        # 先停止所有监控任务
        self.log.info("⏸️ 正在停止所有监控任务...")
        await self.stop_all_monitors()
        self.log.info("✅ 所有监控任务已停止")

        # 并发关闭所有平台（带独立超时控制）
        self.log.info("🔄 正在关闭所有平台...")

        async def close_single_platform(platform: BasePlatform, platform_name: str) -> bool:
            """带超时控制的单个平台关闭"""
            try:
                self.log.info(f"🔒 开始关闭平台：{platform_name}")
                await asyncio.wait_for(platform.close(), timeout=60.0)
                self.log.info(f"✅ 平台 {platform_name} 已关闭")
                return True
            except asyncio.TimeoutError:
                self.log.error(f"❌ 关闭平台 {platform_name} 超时（60 秒），已跳过")
                return False
            except Exception as e:
                self.log.error(f"❌ 关闭平台 {platform_name} 失败：{e}", exc_info=True)
                return False

        # 并发关闭所有平台
        close_tasks = [
            close_single_platform(info.instance, name)
            for name, info in self.platforms.items()
        ]
        results = await asyncio.gather(*close_tasks, return_exceptions=True)

        # 统计关闭结果
        success_count = sum(1 for r in results if r is True)
        failed_count = len(results) - success_count
        self.log.info(f"✅ 平台关闭完成：成功 {success_count} 个，失败 {failed_count} 个")

        # 关闭浏览器（带超时控制）
        if self.driver:
            self.log.info("🚪 正在关闭浏览器...")
            try:
                await asyncio.wait_for(self.driver.quit(), timeout=30.0)
                self.log.info("✅ 浏览器已关闭")
            except asyncio.TimeoutError:
                self.log.error("❌ 关闭浏览器超时（30 秒）")
            except Exception as e:
                self.log.error(f"❌ 关闭浏览器失败：{e}", exc_info=True)

        self.log.info("✅ 所有资源已关闭")
        self._print_task_stats()

    def _print_task_stats(self):
        """打印任务统计信息"""
        if self.task_stats.start_time and self.task_stats.end_time:
            duration = self.task_stats.end_time - self.task_stats.start_time
            self.log.info("=" * 40)
            self.log.info("📊 任务统计:")
            self.log.info(f"   总任务数：{self.task_stats.total_tasks}")
            self.log.info(f"   成功：{self.task_stats.success_tasks}")
            self.log.info(f"   失败：{self.task_stats.failed_tasks}")
            self.log.info(f"   运行时长：{duration}")

            if self.task_stats.total_tasks > 0:
                success_rate = (self.task_stats.success_tasks / self.task_stats.total_tasks) * 100
                self.log.info(f"   成功率：{success_rate:.2f}%")

            self.log.info("=" * 40)

    def get_platform(self, name: str) -> Optional[BasePlatform]:
        """获取平台实例"""
        if name not in self.platforms:
            return None
        return self.platforms[name].instance

    def list_platforms(self) -> List[str]:
        """列出所有平台名称"""
        return list(self.platforms.keys())

    def get_platform_count(self) -> int:
        """获取平台数量"""
        return len(self.platforms)

    def is_platform_registered(self, platform_name: str) -> bool:
        """检查平台是否已注册"""
        return platform_name in self.platforms

    def get_task_stats(self) -> Dict[str, Any]:
        """获取任务统计信息"""
        return self.task_stats.to_dict()

    def save_platform_configs(self, filepath: str) -> bool:
        """保存平台配置到文件"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.platform_configs, f, ensure_ascii=False, indent=2)
            self.log.info(f"✅ 平台配置已保存到：{filepath}")
            return True
        except Exception as e:
            self.log.error(f"保存平台配置失败：{e}", exc_info=True)
            return False

    def load_platform_configs(self, filepath: str) -> Dict[str, Dict[str, Any]]:
        """从文件加载平台配置"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                configs = json.load(f)
            self.log.info(f"✅ 从 {filepath} 加载平台配置")
            return configs
        except Exception as e:
            self.log.error(f"加载平台配置失败：{e}", exc_info=True)
            return {}

    async def batch_register_from_config(self, platform_classes: Dict[str, type[BasePlatform]],
                                         config_file: str) -> bool:
        """批量从配置文件注册平台"""
        configs = self.load_platform_configs(config_file)
        if not configs:
            return False

        success_count = 0
        for platform_name, config_data in configs.items():
            config_data.pop('save_config', None)

            # 获取运行模式（如果有）
            mode_str = config_data.pop('mode', 'MONITOR_AND_PUBLISH')
            mode = PlatformMode[mode_str]

            if platform_name in platform_classes:
                try:
                    await self.register_platform(
                        platform_name=platform_name,
                        platform_class=platform_classes[platform_name],
                        mode=mode,  # 传入模式参数
                        **config_data
                    )
                    success_count += 1
                except Exception as e:
                    self.log.error(f"注册平台 {platform_name} 失败：{e}")
            else:
                self.log.warning(f"未找到平台类：{platform_name}")

        self.log.info(f"批量注册完成：成功 {success_count}/{len(configs)} 个平台")
        return success_count == len(configs)

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.init()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close_all()
        if exc_val:
            self.log.error(f"程序执行异常：{exc_val}")
        return False


# ==================== 测试代码 ====================
if __name__ == '__main__':
    from app.Bloggers.ZhihuBlogger.Control import ZhihuAsyncControl
    import warnings
    import sys
    import signal

    # 抑制 asyncio 的 ResourceWarning
    warnings.filterwarnings("ignore", category=ResourceWarning, message="unclosed transport")
    warnings.filterwarnings("ignore", category=ResourceWarning, message="unclosed event loop")
    warnings.filterwarnings("ignore", category=ResourceWarning, message="unclosed subprocess")

    # 全局变量，用于标记是否收到退出信号
    should_exit = False


    def signal_handler(signum, frame):
        """处理 SIGINT 信号（Ctrl+C）"""
        global should_exit
        if not should_exit:
            should_exit = True
            print("\n\n⚠️  收到退出信号，正在安全关闭...")
            print("⏳ 请稍候，正在保存数据和关闭资源...")


    # 注册信号处理函数
    signal.signal(signal.SIGINT, signal_handler)


    async def check_exit():
        """通用退出检查函数"""
        global should_exit
        if should_exit:
            raise RuntimeError("收到退出信号，终止初始化流程")


    async def main():
        global should_exit
        manager = None
        try:
            # 创建管理器
            manager = MultiPlatformManager(
                md_path=r'D:\pythonproject\Ai_Blogger\Md',
                base_driver_path=r'D:\pythonproject\Ai_Blogger\driver\playwright_data'
            )

            # 初始化
            await manager.init()
            await check_exit()

            # 注册知乎平台（使用新的 mode 参数）
            await manager.register_platform(
                platform_name='zhihu',
                platform_class=ZhihuAsyncControl,
                user_data_dir='zhihu_data',
                mode=PLATFORM_MODE_MONITOR_ONLY,  # 新增参数
                save_config=True
            )
            await check_exit()

            # 启动监控
            await manager.start_monitor('zhihu', interval=DEFAULT_MONITOR_INTERVAL)
            await check_exit()

            # 打印平台信息
            print("\n📊 平台信息:")
            print(json.dumps(manager.get_all_platforms_info(), indent=2, ensure_ascii=False))

            print("\n📈 资源统计:")
            print(json.dumps(manager.get_resource_stats(), indent=2, ensure_ascii=False))

            print("✅ 监控正在运行，按 Ctrl+C 停止...")

            # 定期检查是否收到退出信号
            while not should_exit:
                await asyncio.sleep(1)

        except RuntimeError as e:
            if "收到退出信号" in str(e):
                print(f"\nℹ️  {e}")
            else:
                print(f"\n❌ 运行时错误：{e}")
        except Exception as e:
            print(f"\n❌ 初始化或运行过程中出错：{e}")
            should_exit = True
        finally:
            if manager is not None:
                try:
                    print("\n🔄 正在安全关闭所有资源...")
                    await asyncio.wait_for(manager.close_all(), timeout=120.0)
                    print("\n✅ 程序已安全退出")
                except asyncio.TimeoutError:
                    print("\n⚠️  关闭操作超时，强制退出")
                except Exception as e:
                    print(f"\n❌ 退出时出错：{e}")
            sys.exit(0)


    asyncio.run(main())
