import argparse
import asyncio

from app.core.PromptManager import get_prompt_manager
from app.cli.utils.helper import (
    print_json,
    get_known_platforms,
    create_manager,
    close_manager,
)


def register_subparser(subparsers: argparse._SubParsersAction):
    parser = subparsers.add_parser("status", help="查看系统整体状态")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    parser.set_defaults(func=handle_status)


def handle_status(args):
    return asyncio.run(_async_status(args))


async def _async_status(args):
    pm = get_prompt_manager()
    prompts = pm.list_prompts()
    known_platforms = get_known_platforms()

    resource_stats = {}
    try:
        manager = await create_manager()
        try:
            resource_stats = manager.get_resource_stats()
            platform_info = manager.get_all_platforms_info()
            resource_stats["platforms_info"] = platform_info
        finally:
            await close_manager(manager)
    except Exception:
        resource_stats = {
            "platform_count": 0,
            "active_monitors": 0,
            "task_stats": {"total_tasks": 0, "success_tasks": 0, "failed_tasks": 0},
            "platforms_info": [],
        }

    if args.json:
        print_json({
            "configured_platforms": list(known_platforms.keys()),
            "registered_prompts": len(prompts),
            "resources": resource_stats,
        })
        return

    print("=== AI-Blogger 系统状态 ===")
    print()
    print(f"配置的平台:    {', '.join(known_platforms.keys()) or '无'}")
    print(f"注册的提示词:  {len(prompts)}")
    print(f"活跃监控数:    {resource_stats.get('active_monitors', 0)}")
    print(f"平台实例数:    {resource_stats.get('platform_count', 0)}")
    ts = resource_stats.get("task_stats", {})
    print(f"任务统计:      {ts.get('total_tasks', 0)} 总 / "
          f"{ts.get('success_tasks', 0)} 成功 / "
          f"{ts.get('failed_tasks', 0)} 失败")
