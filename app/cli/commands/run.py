import argparse
import asyncio

from app.cli.utils.helper import (
    create_manager,
    close_manager,
    resolve_platform_class,
    parse_platform_mode,
    get_publish_type_value,
)


def register_subparser(subparsers: argparse._SubParsersAction):
    parser = subparsers.add_parser("run", help="启动主监控循环（阻塞直到 Ctrl+C）")
    parser.add_argument(
        "--platform", "-p", nargs="+",
        default=["zhihu", "weibo"],
        help="要运行的平台（默认: zhihu weibo）",
    )
    parser.add_argument(
        "--interval", "-i", type=int, default=600,
        help="监控检查间隔秒数（默认: 600）",
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["monitor_only", "publish_only", "monitor_and_publish"],
        default="monitor_and_publish",
        help="运行模式（默认: monitor_and_publish）",
    )
    parser.set_defaults(func=handle_run)


def handle_run(args):
    return asyncio.run(_async_run(args))


async def _async_run(args):
    mode = parse_platform_mode(args.mode)
    manager = await create_manager()

    try:
        for platform_name in args.platform:
            control_class, publish_type_enum = resolve_platform_class(platform_name)
            publish_value = get_publish_type_value(platform_name, publish_type_enum)
            await manager.register_platform(
                platform_name=platform_name,
                platform_class=control_class,
                user_data_dir=f"{platform_name}_data",
                mode=mode,
                publish_type=publish_value,
            )

        intervals = {name: args.interval for name in args.platform}
        await manager.start_all_monitors(intervals)

        platform_list = ", ".join(args.platform)
        print(f"AI-Blogger 监控已启动 — 平台: [{platform_list}] | "
              f"间隔: {args.interval}s | 模式: {args.mode}")
        print("按 Ctrl+C 停止。")

        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\n正在关闭…")
    finally:
        await close_manager(manager)
        print("已安全退出。")
