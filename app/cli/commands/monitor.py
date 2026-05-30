import argparse
import asyncio

from app.cli.utils.helper import (
    print_json,
    create_manager,
    close_manager,
    resolve_platform_class,
    get_publish_type_value,
)


def register_subparser(subparsers: argparse._SubParsersAction):
    parser = subparsers.add_parser("monitor", help="控制平台监控")
    sub = parser.add_subparsers(dest="monitor_action", required=True)

    # monitor start
    p_start = sub.add_parser("start", help="启动平台监控（阻塞直到 Ctrl+C）")
    p_start.add_argument("name", help="平台名称")
    p_start.add_argument("--interval", "-i", type=int, default=600, help="检查间隔秒数")
    p_start.set_defaults(func=handle_monitor_start)

    # monitor stop
    p_stop = sub.add_parser("stop", help="停止平台监控")
    p_stop.add_argument("name", help="平台名称")
    p_stop.set_defaults(func=handle_monitor_stop)

    # monitor status
    p_status = sub.add_parser("status", help="查看监控运行状态")
    p_status.add_argument("name", nargs="?", default=None, help="平台名称（可选）")
    p_status.add_argument("--json", action="store_true", help="JSON 格式输出")
    p_status.set_defaults(func=handle_monitor_status)


def handle_monitor_start(args):
    return asyncio.run(_async_monitor_start(args))


def handle_monitor_stop(args):
    return asyncio.run(_async_monitor_stop(args))


def handle_monitor_status(args):
    return asyncio.run(_async_monitor_status(args))


async def _async_monitor_start(args):
    manager = await create_manager()
    try:
        control_class, publish_type_enum = resolve_platform_class(args.name)
        if not manager.is_platform_registered(args.name):
            await manager.register_platform(
                platform_name=args.name,
                platform_class=control_class,
                user_data_dir=f"{args.name}_data",
            )

        success = await manager.start_monitor(args.name, interval=args.interval)
        if success:
            print(f"监控已启动: '{args.name}'（间隔 {args.interval}s），按 Ctrl+C 停止。")
        else:
            print(f"启动监控失败: '{args.name}'。")
            return 1

        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\n正在停止监控...")
    finally:
        await close_manager(manager)


async def _async_monitor_stop(args):
    manager = await create_manager()
    try:
        success = await manager.stop_monitor(args.name)
        if success:
            print(f"监控已停止: '{args.name}'。")
        else:
            print(f"未找到 '{args.name}' 的运行监控。")
            return 1
    except Exception as e:
        print(f"停止监控失败: {e}")
        return 1
    finally:
        await close_manager(manager)


async def _async_monitor_status(args):
    manager = await create_manager()
    try:
        if args.name:
            running = manager.get_monitor_status(args.name)
            data = {args.name: running}
        else:
            running_list = manager.list_running_monitors()
            data = {name: True for name in running_list}

        if args.json:
            print_json(data)
            return

        if not data:
            print("没有运行中的监控。")
            return

        for name, running in data.items():
            status_str = "运行中" if running else "已停止"
            print(f"  {name:<12} {status_str}")
    finally:
        await close_manager(manager)
