import asyncio
import logging
from typing import Dict, List, Any, Optional, Callable, Set
from pathlib import Path
import json
from datetime import datetime
from enum import Enum, auto
from dataclasses import dataclass, field

from app.core.playwright_driver import AsyncPlaywrightDriver
from app.bloggers.base_platform import BasePlatform
from app.tools.logging_config import LoggingConfig
from app.core.config_manager import config
from app.bloggers.base_platform import PlatformMode


# ==================== 常量定义 ====================
@dataclass(frozen=True)
class ManagerConfig:
    """管理器配置常量"""
    DEFAULT_MONITOR_INTERVAL: int = 600
    DEFAULT_MONITOR_TIMEOUT: int = 600
    DEFAULT_PUBLISH_TIMEOUT: int = 300
    DEFAULT_MAX_RETRIES: int = 2
    DEFAULT_SLEEP_MIN: float = 2.0
    DEFAULT_SLEEP_MAX: float = 5.0
    PLATFORM_CLOSE_TIMEOUT: float = 60.0
    BROWSER_CLOSE_TIMEOUT: float = 30.0
    MONITOR_STOP_TIMEOUT: float = 5.0
    BACKGROUND_TASK_TIMEOUT: float = 15.0


# ==================== 数据类 ====================
@dataclass
class PlatformInfo:
    """平台信息封装"""
    name: str
    instance: BasePlatform
    mode: PlatformMode
    registered_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)

    def update_activity(self):
        """更新最后活动时间"""
        self.last_activity = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'mode': self.mode.value,
            'registered_at': self.registered_at.isoformat(),
            'last_activity': self.last_activity.isoformat()
        }


@dataclass
class TaskStats:
    """任务统计信息"""
    total_tasks: int = 0
    success_tasks: int = 0
    failed_tasks: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    def reset(self):
        """重置统计数据"""
        self.total_tasks = 0
        self.success_tasks = 0
        self.failed_tasks = 0
        self.start_time = None
        self.end_time = None

    def record_success(self):
        """记录成功任务"""
        self.total_tasks += 1
        self.success_tasks += 1

    def record_failure(self):
        """记录失败任务"""
        self.total_tasks += 1
        self.failed_tasks += 1

    @property
    def success_rate(self) -> float:
        """计算成功率"""
        if self.total_tasks == 0:
            return 0.0
        return (self.success_tasks / self.total_tasks) * 100

    @property
    def duration(self) -> Optional[str]:
        """计算运行时长"""
        if self.start_time and self.end_time:
            return str(self.end_time - self.start_time)
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_tasks': self.total_tasks,
            'success_tasks': self.success_tasks,
            'failed_tasks': self.failed_tasks,
            'duration': self.duration,
            'success_rate': f"{self.success_rate:.2f}%"
        }


class MonitorStatus:
    """监控任务状态管理"""

    def __init__(self):
        self._running_monitors: Dict[str, bool] = {}
        self._monitor_tasks: Dict[str, asyncio.Task] = {}

    def is_running(self, platform_name: str) -> bool:
        """检查监控是否正在运行"""
        if platform_name not in self._monitor_tasks:
            return False
        return not self._monitor_tasks[platform_name].done()

    def set_running(self, platform_name: str, task: asyncio.Task):
        """设置监控为运行状态"""
        self._running_monitors[platform_name] = True
        self._monitor_tasks[platform_name] = task

    def stop(self, platform_name: str):
        """停止监控"""
        self._running_monitors[platform_name] = False

    def should_continue(self, platform_name: str) -> bool:
        """检查是否应继续监控"""
        return self._running_monitors.get(platform_name, False)

    def get_task(self, platform_name: str) -> Optional[asyncio.Task]:
        """获取监控任务"""
        return self._monitor_tasks.get(platform_name)

    def remove_task(self, platform_name: str):
        """移除监控任务"""
        self._monitor_tasks.pop(platform_name, None)
        self._running_monitors.pop(platform_name, None)

    def get_all_running(self) -> List[str]:
        """获取所有正在运行的监控"""
        return [
            name for name, task in self._monitor_tasks.items()
            if not task.done()
        ]

    def get_active_count(self) -> int:
        """获取活跃监控数量"""
        return len([t for t in self._monitor_tasks.values() if not t.done()])


class EventBus:
    """事件总线 - 观察者模式实现"""

    def __init__(self, logger: logging.Logger):
        self._callbacks: Dict[str, List[Callable]] = {
            'platform_registered': [],
            'platform_unregistered': [],
            'monitor_started': [],
            'monitor_stopped': [],
            'publish_completed': [],
        }
        self._logger = logger

    def register(self, event: str, callback: Callable) -> None:
        """注册回调函数"""
        if event in self._callbacks:
            self._callbacks[event].append(callback)
            self._logger.info(f"✅ 回调函数已注册：{event}")
        else:
            self._logger.warning(f"⚠️ 未知事件：{event}")

    async def emit(self, event: str, data: Any = None) -> None:
        """触发事件"""
        if event not in self._callbacks:
            return

        for callback in self._callbacks[event]:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                self._logger.error(f"回调函数执行失败 ({event}): {e}", exc_info=True)


class PlatformFactory:
    """平台工厂 - 负责创建和配置平台实例"""

    def __init__(self, driver: AsyncPlaywrightDriver, base_driver_path: Path, logger: logging.Logger):
        self.driver = driver
        self.base_driver_path = base_driver_path
        self.logger = logger

    async def create_platform(
            self,
            platform_name: str,
            platform_class: type[BasePlatform],
            user_data_dir: str,
            viewport_type: str = "pc",
            custom_ua: Optional[str] = None,
            mode: PlatformMode = PlatformMode.MONITOR_AND_PUBLISH,
            publish_type: Any = None,
            **kwargs: Any
    ) -> tuple[BasePlatform, Path]:
        """
        创建平台实例

        Returns:
            tuple: (平台实例, 平台数据目录路径)
        """
        try:
            # 构建完整的平台数据目录路径
            platform_data_path = self.base_driver_path / user_data_dir
            platform_data_path.mkdir(parents=True, exist_ok=True)

            # 创建独立的持久化 Context
            context = await self.driver.create_platform_context(
                platform_name=platform_name,
                user_data_dir=str(platform_data_path),
                viewport_type=viewport_type,
                custom_ua=custom_ua
            )

            # 创建平台实例
            platform_instance = platform_class(
                context=context,
                mode=mode,
                user_data_dir=str(platform_data_path),
                publish_type=publish_type
            )

            self.logger.info(f"✅ 平台 {platform_name} 实例创建成功")
            return platform_instance, platform_data_path

        except Exception as e:
            self.logger.error(f"创建平台 {platform_name} 失败：{e}", exc_info=True)
            raise


# ==================== 主管理类 ====================
class MultiPlatformManager:
    """
    多平台并发管理器 v3.0

    核心功能:
    1. 单 Browser + 多 Context 架构（资源高效利用）
    2. 统一管理所有平台的生命周期
    3. 并发执行任务，故障隔离
    4. 支持动态添加/移除平台
    5. 任务队列和重试机制
    6. 状态监控和统计
    7. 分离监控任务和发布任务
    8. 支持多种运行模式（只监控、只发布、监控 + 发布）

    架构设计:
    - PlatformFactory: 负责平台实例创建
    - MonitorStatus: 管理监控任务状态
    - EventBus: 事件通知系统
    - TaskStats: 任务统计
    - MultiPlatformManager: 协调各组件

    使用示例:
        async with MultiPlatformManager(md_path='./Md', base_driver_path='./driver') as manager:
            await manager.register_platform(
                platform_name='zhihu',
                platform_class=ZhihuAsyncControl,
                user_data_dir='zhihu_data',
                mode=PlatformMode.MONITOR_AND_PUBLISH
            )
            await manager.start_monitor('zhihu', interval=600)
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

        # 核心组件
        self.driver: Optional[AsyncPlaywrightDriver] = None
        self.browser = None
        self.platform_factory: Optional[PlatformFactory] = None
        self.monitor_status = MonitorStatus()
        self.event_bus: Optional[EventBus] = None

        # 平台管理
        self.platforms: Dict[str, PlatformInfo] = {}
        self.platform_configs: Dict[str, Dict[str, Any]] = {}

        # 任务统计
        self.task_stats = TaskStats()

        # 日志
        self.log = LoggingConfig(log_file_path=config.logfile_path, log_level=config.log_level).get_logger(
            self.__class__.__name__)

    async def init(self) -> None:
        """
        初始化多平台管理器

        Raises:
            Exception: 初始化失败时抛出异常
        """
        try:
            self.task_stats.start_time = datetime.now()
            self.base_driver_path.mkdir(parents=True, exist_ok=True)

            # 启动浏览器
            self.driver = AsyncPlaywrightDriver(base_data_dir=str(self.base_driver_path))
            self.browser, _, _ = await self.driver.launch_browser()

            # 初始化组件
            self.platform_factory = PlatformFactory(self.driver, self.base_driver_path, self.log)
            self.event_bus = EventBus(self.log)

            self.log.info("✅ 多平台管理器初始化成功")

            # 触发事件
            await self.event_bus.emit('platform_registered', None)

        except Exception as e:
            self.log.error(f"初始化失败：{e}", exc_info=True)
            raise

    async def register_platform(self,
                                platform_name: str,
                                platform_class: type[BasePlatform],
                                user_data_dir: str,
                                viewport_type: str = "pc",
                                custom_ua: Optional[str] = None,
                                mode: PlatformMode = PlatformMode.MONITOR_AND_PUBLISH,
                                publish_type: Any = None,
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
            publish_type: 发布类型
            save_config: 是否保存配置
        """
        if platform_name in self.platforms:
            self.log.warning(f"平台 {platform_name} 已存在，将先移除旧实例")
            await self.unregister_platform(platform_name)

        try:
            # 使用工厂创建平台
            platform_instance, platform_data_path = await self.platform_factory.create_platform(
                platform_name=platform_name,
                platform_class=platform_class,
                user_data_dir=user_data_dir,
                viewport_type=viewport_type,
                custom_ua=custom_ua,
                mode=mode,
                publish_type=publish_type,
                **kwargs
            )

            # 注册平台
            self.platforms[platform_name] = PlatformInfo(
                name=platform_name,
                instance=platform_instance,
                mode=mode
            )

            # 保存配置
            if save_config:
                self.platform_configs[platform_name] = {
                    'class_name': platform_class.__name__,
                    'user_data_dir': user_data_dir,
                    'viewport_type': viewport_type,
                    'custom_ua': custom_ua,
                    'mode': mode.value,
                    'kwargs': kwargs,
                    'registered_at': datetime.now().isoformat()
                }

            self.log.info(f"✅ 平台 {platform_name} 注册成功（模式：{mode.value}）")

            # 触发事件
            await self.event_bus.emit('platform_registered', platform_name)

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

            # 关闭平台资源
            platform_info = self.platforms[platform_name]
            await platform_info.instance.close()

            # 清理数据
            del self.platforms[platform_name]
            self.platform_configs.pop(platform_name, None)

            self.log.info(f"✅ 平台 {platform_name} 已移除")

            # 触发事件
            await self.event_bus.emit('platform_unregistered', platform_name)
            return True

        except Exception as e:
            self.log.error(f"移除平台 {platform_name} 失败：{e}", exc_info=True)
            return False

    async def publish_to_all(self, content: Dict[str, Any], timeout: int = ManagerConfig.DEFAULT_PUBLISH_TIMEOUT) -> \
            Dict[str, bool]:
        """并发发布到所有平台"""
        results = {}

        if not self.platforms:
            self.log.warning("没有已注册的平台")
            return results

        # 过滤出支持发布的平台
        publishable_platforms = {
            name: info for name, info in self.platforms.items()
            if info.mode in (PlatformMode.PUBLISH_ONLY, PlatformMode.MONITOR_AND_PUBLISH)
        }

        if not publishable_platforms:
            self.log.warning("没有支持发布的平台")
            return results

        self.log.info(f"🚀 开始并发发布到 {len(publishable_platforms)} 个平台...")

        # 创建发布任务
        tasks = {
            name: self._publish_with_retry(info.instance, content)
            for name, info in publishable_platforms.items()
        }

        try:
            completed_tasks = await asyncio.wait_for(
                asyncio.gather(*tasks.values(), return_exceptions=True),
                timeout=timeout
            )

            # 处理结果
            for (name, _), result in zip(tasks.items(), completed_tasks):
                success = self._handle_publish_result(name, result)
                results[name] = success

        except asyncio.TimeoutError:
            self.log.error(f"发布超时（{timeout}秒）")
            for name in publishable_platforms.keys():
                results[name] = False
                self.task_stats.record_failure()

        finally:
            await self.event_bus.emit('publish_completed', results)

        return results

    async def publish_to_platform(self, platform_name: str, content: Dict[str, Any],
                                  max_retries: int = ManagerConfig.DEFAULT_MAX_RETRIES) -> bool:
        """发布到指定平台"""
        if platform_name not in self.platforms:
            self.log.error(f"平台 {platform_name} 未注册")
            return False

        platform_info = self.platforms[platform_name]

        # 检查平台模式
        if platform_info.mode == PlatformMode.MONITOR_ONLY:
            self.log.error(f"平台 {platform_name} 处于只监控模式，不支持发布")
            return False

        success = await self._publish_with_retry(platform_info.instance, content, max_retries)

        if success:
            self.task_stats.record_success()
        else:
            self.task_stats.record_failure()

        return success

    async def _publish_with_retry(self, platform: BasePlatform, content: Dict[str, Any],
                                  max_retries: int = ManagerConfig.DEFAULT_MAX_RETRIES,
                                  url: Optional[str] = None) -> bool:
        """带重试机制的发布方法"""
        for attempt in range(max_retries):
            try:
                success = await platform.publish_content(content, url)
                if success:
                    return True

                self.log.warning(f"发布失败（第{attempt + 1}/{max_retries}次尝试）")

            except Exception as e:
                self.log.warning(f"发布异常（第{attempt + 1}/{max_retries}次尝试）: {e}")

            # 重试前等待
            if attempt < max_retries - 1:
                await platform.random_sleep(
                    ManagerConfig.DEFAULT_SLEEP_MIN,
                    ManagerConfig.DEFAULT_SLEEP_MAX
                )

        return False

    def _handle_publish_result(self, platform_name: str, result: Any) -> bool:
        """处理发布结果"""
        if isinstance(result, Exception):
            self.task_stats.record_failure()
            self.log.error(f"❌ 平台 {platform_name} 发布失败：{result}")
            return False

        success = bool(result)
        if success:
            self.task_stats.record_success()
            self.log.info(f"✅ 平台 {platform_name} 发布成功")
        else:
            self.task_stats.record_failure()
            self.log.error(f"❌ 平台 {platform_name} 发布失败")

        return success

    async def start_monitor(self, platform_name: str, interval: int = ManagerConfig.DEFAULT_MONITOR_INTERVAL) -> bool:
        """启动指定平台的监控任务"""
        if platform_name not in self.platforms:
            self.log.error(f"平台 {platform_name} 未注册")
            return False

        platform_info = self.platforms[platform_name]

        # 检查平台模式
        if platform_info.mode == PlatformMode.PUBLISH_ONLY:
            self.log.error(f"平台 {platform_name} 处于只发布模式，不支持监控")
            return False

        # 检查是否已在运行
        if self.monitor_status.is_running(platform_name):
            self.log.warning(f"平台 {platform_name} 的监控任务已在运行")
            return False

        platform = platform_info.instance

        try:
            # 创建监控任务
            task = asyncio.create_task(self._monitor_loop(platform_name, platform, interval))
            self.monitor_status.set_running(platform_name, task)

            self.log.info(f"✅ 平台 {platform_name} 监控任务已启动（间隔：{interval}秒）")

            # 触发事件
            await self.event_bus.emit('monitor_started', platform_name)
            return True

        except Exception as e:
            self.log.error(f"启动监控任务失败：{e}", exc_info=True)
            self.monitor_status.stop(platform_name)
            return False

    async def _monitor_loop(self, platform_name: str, platform: BasePlatform, interval: int) -> None:
        """监控任务循环"""
        count = 0
        while self.monitor_status.should_continue(platform_name):
            count += 1
            self.log.info(f"[{platform_name}] 🔍 第 {count} 次检测")

            try:
                start_time = datetime.now()

                # 调用平台的 run() 方法
                await platform.run()

                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                self.log.debug(f"[{platform_name}] run() 执行完成，耗时 {duration:.2f}秒")

            except asyncio.TimeoutError:
                self.log.warning(f"[{platform_name}] run() 执行超时（>{ManagerConfig.DEFAULT_MONITOR_TIMEOUT} 秒）")

            except Exception as e:
                self.log.error(f"[{platform_name}] 监控任务失败：{e}", exc_info=True)

            # 检查是否需要继续
            if not self.monitor_status.should_continue(platform_name):
                self.log.info(f"[{platform_name}] 收到停止信号，退出循环")
                break

    async def stop_monitor(self, platform_name: str) -> bool:
        """停止指定平台的监控任务"""
        if not self.monitor_status.is_running(platform_name):
            self.log.warning(f"平台 {platform_name} 没有运行的监控任务")
            return False

        try:
            # 设置停止标志
            self.monitor_status.stop(platform_name)

            # 取消任务
            task = self.monitor_status.get_task(platform_name)
            if task and not task.done():
                task.cancel()
                try:
                    await asyncio.wait_for(task, timeout=ManagerConfig.MONITOR_STOP_TIMEOUT)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
                except Exception as e:
                    self.log.error(f"等待监控任务结束失败：{e}", exc_info=True)

            # 清理状态
            self.monitor_status.remove_task(platform_name)

            self.log.info(f"✅ 平台 {platform_name} 监控任务已停止")

            # 触发事件
            await self.event_bus.emit('monitor_stopped', platform_name)
            return True

        except Exception as e:
            self.log.error(f"停止监控任务失败：{e}", exc_info=True)
            # 确保状态被清理
            self.monitor_status.remove_task(platform_name)
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
        for platform_name in list(self.monitor_status.get_all_running()):
            results[platform_name] = await self.stop_monitor(platform_name)
        return results

    # ==================== 状态查询方法 ====================
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
        total_pages = sum(
            (1 if info.instance.monitor_page and not info.instance.monitor_page.is_closed() else 0) +
            (1 if info.instance.publish_page and not info.instance.publish_page.is_closed() else 0)
            for info in self.platforms.values()
        )

        return {
            'platform_count': len(self.platforms),
            'active_monitors': self.monitor_status.get_active_count(),
            'total_pages': total_pages,
            'task_stats': self.task_stats.to_dict()
        }

    def get_monitor_status(self, platform_name: str) -> bool:
        """获取指定平台监控任务状态"""
        return self.monitor_status.is_running(platform_name)

    def list_running_monitors(self) -> List[str]:
        """列出所有正在运行的监控任务"""
        return self.monitor_status.get_all_running()

    def register_callback(self, event: str, callback: Callable) -> None:
        """
        注册回调函数

        支持的事件:
        - platform_registered: 平台注册成功
        - platform_unregistered: 平台移除成功
        - monitor_started: 监控任务启动
        - monitor_stopped: 监控任务停止
        - publish_completed: 发布完成
        """
        if self.event_bus:
            self.event_bus.register(event, callback)

    async def close_all(self) -> None:
        """关闭所有平台和资源"""
        self.log.info("正在关闭所有平台...")
        self.task_stats.end_time = datetime.now()

        # 停止所有监控任务
        await self._stop_all_monitors_safe()

        # 关闭所有平台
        await self._close_all_platforms_safe()

        # 关闭浏览器
        await self._close_browser_safe()

        self.log.info("✅ 所有资源已关闭")
        self._print_task_stats()

    async def _stop_all_monitors_safe(self):
        """安全停止所有监控任务"""
        self.log.info("⏸️ 正在停止所有监控任务...")
        await self.stop_all_monitors()
        self.log.info("✅ 所有监控任务已停止")

    async def _close_all_platforms_safe(self):
        """安全关闭所有平台"""
        self.log.info("🔄 正在关闭所有平台...")

        async def close_single_platform(platform: BasePlatform, platform_name: str) -> bool:
            """带超时控制的单个平台关闭"""
            try:
                self.log.info(f"🔒 开始关闭平台：{platform_name}")
                await asyncio.wait_for(
                    platform.close(),
                    timeout=ManagerConfig.PLATFORM_CLOSE_TIMEOUT
                )
                self.log.info(f"✅ 平台 {platform_name} 已关闭")
                return True
            except asyncio.TimeoutError:
                self.log.error(f"❌ 关闭平台 {platform_name} 超时（{ManagerConfig.PLATFORM_CLOSE_TIMEOUT} 秒）")
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

        success_count = sum(1 for r in results if r is True)
        failed_count = len(results) - success_count
        self.log.info(f"✅ 平台关闭完成：成功 {success_count} 个，失败 {failed_count} 个")

    async def _close_browser_safe(self):
        """安全关闭浏览器"""
        if not self.driver:
            return

        self.log.info("🚪 正在关闭浏览器...")
        try:
            await asyncio.wait_for(
                self.driver.quit(),
                timeout=ManagerConfig.BROWSER_CLOSE_TIMEOUT
            )
            self.log.info("✅ 浏览器已关闭")
        except asyncio.TimeoutError:
            self.log.error(f"❌ 关闭浏览器超时（{ManagerConfig.BROWSER_CLOSE_TIMEOUT} 秒）")
        except Exception as e:
            self.log.error(f"❌ 关闭浏览器失败：{e}", exc_info=True)

    def _print_task_stats(self):
        """打印任务统计信息"""
        if not self.task_stats.start_time or not self.task_stats.end_time:
            return

        duration = self.task_stats.end_time - self.task_stats.start_time
        self.log.info("=" * 40)
        self.log.info("📊 任务统计:")
        self.log.info(f"   总任务数：{self.task_stats.total_tasks}")
        self.log.info(f"   成功：{self.task_stats.success_tasks}")
        self.log.info(f"   失败：{self.task_stats.failed_tasks}")
        self.log.info(f"   运行时长：{duration}")

        if self.task_stats.total_tasks > 0:
            self.log.info(f"   成功率：{self.task_stats.success_rate:.2f}%")

        self.log.info("=" * 40)

    # ==================== 便捷方法 ====================
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

    # ==================== 配置管理 ====================
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

            # 获取运行模式
            mode_str = config_data.pop('mode', 'MONITOR_AND_PUBLISH')
            try:
                mode = PlatformMode[mode_str]
            except KeyError:
                self.log.warning(f"无效的模式：{mode_str}，使用默认值")
                mode = PlatformMode.MONITOR_AND_PUBLISH

            if platform_name in platform_classes:
                try:
                    await self.register_platform(
                        platform_name=platform_name,
                        platform_class=platform_classes[platform_name],
                        mode=mode,
                        **config_data
                    )
                    success_count += 1
                except Exception as e:
                    self.log.error(f"注册平台 {platform_name} 失败：{e}")
            else:
                self.log.warning(f"未找到平台类：{platform_name}")

        self.log.info(f"批量注册完成：成功 {success_count}/{len(configs)} 个平台")
        return success_count == len(configs)

    # ==================== 异步上下文管理器 ====================
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
    from app.core.config_manager import config
    from app.bloggers.zhihu_blogger.control import ZhihuAsyncControl
    from app.bloggers.weibo_blogger.control import WeiboAsyncControl
    from app.bloggers.zhihu_blogger.publish_type_enums import ZhihuPublishType
    from app.bloggers.weibo_blogger.publish_type_enums import WeiboPublishType

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
                md_path=str(config.project_root / "Md"),
                base_driver_path=str(config.base_driver_path)
            )

            # 初始化
            await manager.init()
            await check_exit()

            # 注册微博平台
            await manager.register_platform(
                platform_name='zhihu',
                platform_class=ZhihuAsyncControl,
                user_data_dir='zhihu_data',
                mode=PlatformMode.MONITOR_AND_PUBLISH,
                save_config=True,
                publish_type=ZhihuPublishType.ARTICLE
            )
            await check_exit()

            # 启动微博监控
            await manager.start_monitor('zhihu', interval=ManagerConfig.DEFAULT_MONITOR_INTERVAL)
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
