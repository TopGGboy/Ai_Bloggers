import asyncio
import logging
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
import json
from datetime import datetime

from app.core.PlaywrightDriver import AsyncPlaywrightDriver
from app.Bloggers.BasePlatform import BasePlatform
from app.tools.LoggingConfig import LoggingConfig
from app.core.config_manager import config


class MultiPlatformManager:
    """
    多平台并发管理器

    核心功能:
    1. 单 Browser + 多 Context 架构
    2. 统一管理所有平台的生命周期
    3. 并发执行任务，故障隔离
    4. 支持动态添加/移除平台
    5. 任务队列和重试机制
    6. 状态监控和统计
    """

    def __init__(self, md_path: str, base_driver_path: str):
        """
        初始化多平台管理器

        Args:
            md_path: Markdown 文件存储路径
            base_driver_path: 浏览器数据根目录
        """
        self.md_path = md_path
        self.base_driver_path = Path(base_driver_path)
        self.driver: Optional[AsyncPlaywrightDriver] = None
        self.browser = None
        self.platforms: Dict[str, BasePlatform] = {}
        self.log = LoggingConfig(log_file_path=config.logfile_path).get_logger("MultiPlatformManager")

        # 任务统计
        self.task_stats = {
            'total_tasks': 0,
            'success_tasks': 0,
            'failed_tasks': 0,
            'start_time': None,
            'end_time': None
        }

        # 平台配置缓存
        self.platform_configs: Dict[str, Dict[str, Any]] = {}

    async def init(self) -> None:
        """
        初始化浏览器和所有平台
        """
        try:
            self.task_stats['start_time'] = datetime.now()

            # 启动单浏览器实例
            self.driver = AsyncPlaywrightDriver()
            self.browser, _, _ = await self.driver.launch_browser()
            self.log.info("✅ 浏览器实例启动成功")

        except Exception as e:
            self.log.error(f"初始化浏览器失败：{e}", exc_info=True)
            raise

    async def register_platform(self,
                                platform_name: str,
                                platform_class: type,
                                user_data_dir: str,
                                viewport_type: str = "pc",
                                custom_ua: Optional[str] = None,
                                save_config: bool = True,
                                **kwargs) -> None:
        """
        注册一个平台

        Args:
            platform_name: 平台名称（如 'zhihu', 'xiaohongshu'）
            platform_class: 平台类（继承自 BasePlatform）
            user_data_dir: 该平台的持久化目录
            viewport_type: pc 或 mobile
            custom_ua: 自定义 UA
            save_config: 是否保存配置到缓存
            **kwargs: 传递给平台构造函数的其他参数
        """
        try:
            # 为该平台创建独立 Context
            context = await self.driver.create_platform_context(
                platform_name=platform_name,
                user_data_dir=str(self.base_driver_path / user_data_dir),
                viewport_type=viewport_type,
                custom_ua=custom_ua
            )

            # 创建平台实例
            platform_instance = platform_class(context=context, md_path=self.md_path, **kwargs)

            # 初始化平台
            await platform_instance.init()

            # 注册到平台字典
            self.platforms[platform_name] = platform_instance

            # 保存配置
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

        except Exception as e:
            self.log.error(f"注册平台 {platform_name} 失败：{e}", exc_info=True)
            raise

    async def unregister_platform(self, platform_name: str) -> bool:
        """
        移除已注册的平台

        Args:
            platform_name: 平台名称

        Returns:
            bool: 是否成功移除
        """
        if platform_name not in self.platforms:
            self.log.warning(f"平台 {platform_name} 不存在")
            return False

        try:
            platform = self.platforms[platform_name]
            await platform.close()
            del self.platforms[platform_name]

            if platform_name in self.platform_configs:
                del self.platform_configs[platform_name]

            self.log.info(f"✅ 平台 {platform_name} 已移除")
            return True

        except Exception as e:
            self.log.error(f"移除平台 {platform_name} 失败：{e}", exc_info=True)
            return False

    async def publish_to_all(self, content: Dict[str, Any], timeout: int = 300) -> Dict[str, bool]:
        """
        并发发布内容到所有已注册平台

        Args:
            content: 内容字典
            timeout: 超时时间（秒）

        Returns:
            Dict[str, bool]: 各平台的发布结果
        """
        results = {}

        if not self.platforms:
            self.log.warning("没有已注册的平台")
            return results

        self.task_stats['total_tasks'] += len(self.platforms)
        self.log.info(f"🚀 开始并发发布到 {len(self.platforms)} 个平台...")

        # 创建所有平台的发布任务
        tasks = {
            name: self._publish_with_retry(platform, content)
            for name, platform in self.platforms.items()
        }

        try:
            # 并发执行，故障隔离
            completed_tasks = await asyncio.wait_for(
                asyncio.gather(*tasks.values(), return_exceptions=True),
                timeout=timeout
            )

            # 收集结果
            for (name, _), result in zip(tasks.items(), completed_tasks):
                if isinstance(result, Exception):
                    results[name] = False
                    self.task_stats['failed_tasks'] += 1
                    self.log.error(f"❌ 平台 {name} 发布失败：{result}")
                else:
                    results[name] = result
                    if result:
                        self.task_stats['success_tasks'] += 1
                    else:
                        self.task_stats['failed_tasks'] += 1

                    status = "✅" if result else "❌"
                    self.log.info(f"{status} 平台 {name} 发布{'成功' if result else '失败'}")

        except asyncio.TimeoutError:
            self.log.error(f"发布超时（{timeout}秒）")
            for name in self.platforms.keys():
                results[name] = False
                self.task_stats['failed_tasks'] += 1

        return results

    async def publish_to_platform(self, platform_name: str, content: Dict[str, Any],
                                  max_retries: int = 2) -> bool:
        """
        发布内容到指定平台

        Args:
            platform_name: 平台名称
            content: 内容字典
            max_retries: 最大重试次数

        Returns:
            bool: 发布是否成功
        """
        if platform_name not in self.platforms:
            self.log.error(f"平台 {platform_name} 未注册")
            return False

        platform = self.platforms[platform_name]
        self.task_stats['total_tasks'] += 1

        success = await self._publish_with_retry(platform, content, max_retries)

        if success:
            self.task_stats['success_tasks'] += 1
        else:
            self.task_stats['failed_tasks'] += 1

        return success

    async def _publish_with_retry(self, platform: BasePlatform, content: Dict[str, Any],
                                  max_retries: int = 2, url: str = None) -> bool:
        """
        带重试的发布逻辑

        Args:
            platform: 平台实例
            content: 内容字典
            max_retries: 最大重试次数
            url: 目标话题链接

        Returns:
            bool: 发布是否成功
        """
        for attempt in range(max_retries):
            try:
                success = await platform.publish_content(content, url)
                if success:
                    return True

            except Exception as e:
                self.log.warning(f"发布失败（第{attempt + 1}次尝试）: {e}")
                if attempt < max_retries - 1:
                    await platform.random_sleep(2, 5)  # 重试前延迟

        return False

    async def run_monitor_task(self, platform_name: str, interval: int = 600) -> None:
        """
        运行单个平台的监控任务（独立协程）

        Args:
            platform_name: 平台名称
            interval: 监控间隔（秒）
        """
        if platform_name not in self.platforms:
            self.log.error(f"平台 {platform_name} 未注册")
            return

        platform = self.platforms[platform_name]
        count = 0

        while True:
            count += 1
            self.log.info(f"[{platform_name}] 第 {count} 次检测")

            try:
                # 调用平台的监控逻辑（需要各平台自行实现）
                if hasattr(platform, 'run_monitor'):
                    await platform.run_monitor()
                else:
                    self.log.warning(f"平台 {platform_name} 未实现 run_monitor 方法")

            except Exception as e:
                self.log.error(f"[{platform_name}] 监控任务失败：{e}", exc_info=True)

            await asyncio.sleep(interval)

    async def monitor_all_platforms(self, intervals: Dict[str, int]) -> None:
        """
        并发监控所有平台

        Args:
            intervals: 各平台的监控间隔（秒）
            例如：{'zhihu': 600, 'xiaohongshu': 900}
        """
        tasks = []
        for platform_name, interval in intervals.items():
            tasks.append(self.run_monitor_task(platform_name, interval))

        await asyncio.gather(*tasks)

    async def close_all(self) -> None:
        """关闭所有平台和浏览器"""
        self.log.info("正在关闭所有平台...")
        self.task_stats['end_time'] = datetime.now()

        # 并发关闭所有平台
        tasks = [platform.close() for platform in self.platforms.values()]
        await asyncio.gather(*tasks)

        # 关闭浏览器
        if self.driver:
            await self.driver.quit()

        self.log.info("✅ 所有资源已关闭")

        # 打印统计信息
        self._print_task_stats()

    def _print_task_stats(self):
        """打印任务统计信息"""
        if self.task_stats['start_time'] and self.task_stats['end_time']:
            duration = self.task_stats['end_time'] - self.task_stats['start_time']
            self.log.info("=" * 40)
            self.log.info("📊 任务统计:")
            self.log.info(f"   总任务数：{self.task_stats['total_tasks']}")
            self.log.info(f"   成功：{self.task_stats['success_tasks']}")
            self.log.info(f"   失败：{self.task_stats['failed_tasks']}")
            self.log.info(f"   运行时长：{duration}")

            if self.task_stats['total_tasks'] > 0:
                success_rate = (self.task_stats['success_tasks'] / self.task_stats['total_tasks']) * 100
                self.log.info(f"   成功率：{success_rate:.2f}%")

            self.log.info("=" * 40)

    def get_platform(self, name: str) -> Optional[BasePlatform]:
        """获取指定平台实例"""
        return self.platforms.get(name)

    def list_platforms(self) -> List[str]:
        """列出所有已注册平台"""
        return list(self.platforms.keys())

    def get_platform_count(self) -> int:
        """获取已注册平台数量"""
        return len(self.platforms)

    def is_platform_registered(self, platform_name: str) -> bool:
        """检查平台是否已注册"""
        return platform_name in self.platforms

    def get_task_stats(self) -> Dict[str, Any]:
        """获取任务统计信息"""
        return self.task_stats.copy()

    def save_platform_configs(self, filepath: str) -> bool:
        """
        保存平台配置到文件

        Args:
            filepath: 保存路径

        Returns:
            bool: 是否保存成功
        """
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.platform_configs, f, ensure_ascii=False, indent=2)
            self.log.info(f"✅ 平台配置已保存到：{filepath}")
            return True
        except Exception as e:
            self.log.error(f"保存平台配置失败：{e}", exc_info=True)
            return False

    def load_platform_configs(self, filepath: str) -> Dict[str, Dict[str, Any]]:
        """
        从文件加载平台配置

        Args:
            filepath: 配置文件路径

        Returns:
            Dict: 平台配置字典
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                configs = json.load(f)
            self.log.info(f"✅ 从 {filepath} 加载平台配置")
            return configs
        except Exception as e:
            self.log.error(f"加载平台配置失败：{e}", exc_info=True)
            return {}

    async def batch_register_from_config(self, platform_classes: Dict[str, type],
                                         config_file: str) -> bool:
        """
        从配置文件批量注册平台

        Args:
            platform_classes: 平台类映射 {platform_name: platform_class}
            config_file: 配置文件路径

        Returns:
            bool: 是否全部注册成功
        """
        configs = self.load_platform_configs(config_file)
        if not configs:
            return False

        success_count = 0
        for platform_name, config_data in configs.items():

            # 移除 save_config 参数，避免重复保存
            config_data.pop('save_config', None)

            if platform_name in platform_classes:
                try:
                    await self.register_platform(
                        platform_name=platform_name,
                        platform_class=platform_classes[platform_name],
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


if __name__ == '__main__':
    from app.Bloggers.ZhihuBlogger.Control import ZhihuAsyncControl


    # 使用方式 1：手动管理

    async def main():
        manager = MultiPlatformManager(
            md_path=r'D:\pythonproject\Ai_Blogger\Md',
            base_driver_path=r'D:\pythonproject\Ai_Blogger\driver\playwright_data'
        )

        await manager.init()

        # 注册平台
        await manager.register_platform(
            platform_name='zhihu',
            platform_class=ZhihuAsyncControl,
            user_data_dir='zhihu_data'
        )

        results = await manager.publish_to_all(content)

        # 查看统计
        stats = manager.get_task_stats()
        print(stats)

        await manager.close_all()


    asyncio.run(main())


