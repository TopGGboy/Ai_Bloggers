import argparse
import asyncio

from app.cli.utils.helper import (
    print_json,
    mask_sensitive,
    create_manager,
    close_manager,
    resolve_platform_class,
    parse_platform_mode,
    get_known_platforms,
    get_sensitive_leaf_keys,
    deep_mask_config,
)


def register_subparser(subparsers: argparse._SubParsersAction):
    parser = subparsers.add_parser("platform", help="管理平台")
    sub = parser.add_subparsers(dest="platform_action", required=True)

    # platform list
    p_list = sub.add_parser("list", help="列出所有已配置平台")
    p_list.add_argument("--json", action="store_true", help="JSON 格式输出")
    p_list.set_defaults(func=handle_platform_list)

    # platform info
    p_info = sub.add_parser("info", help="查看平台详细信息")
    p_info.add_argument("name", help="平台名称")
    p_info.add_argument("--json", action="store_true", help="JSON 格式输出")
    p_info.set_defaults(func=handle_platform_info)

    # platform register
    p_reg = sub.add_parser("register", help="注册平台（需浏览器环境）")
    p_reg.add_argument("name", help="平台名称")
    p_reg.set_defaults(func=handle_platform_register)

    # platform unregister
    p_unreg = sub.add_parser("unregister", help="注销平台")
    p_unreg.add_argument("name", help="平台名称")
    p_unreg.set_defaults(func=handle_platform_unregister)


def handle_platform_list(args):
    platforms = get_known_platforms()
    if args.json:
        print_json(platforms)
        return

    if not platforms:
        print("未配置任何平台。")
        return

    print(f"{'平台':<12} {'登录方式':<18} {'检查间隔':<14}")
    print("-" * 44)
    for name, cfg in platforms.items():
        login_type = cfg.get("login_type", "N/A")
        interval = f"{cfg.get('check_interval', 'N/A')}s"
        print(f"{name:<12} {login_type:<18} {interval:<14}")


def handle_platform_info(args):
    platforms = get_known_platforms()
    if args.name not in platforms:
        print(f"配置中未找到平台 '{args.name}'。")
        return 1

    cfg = platforms[args.name]
    sensitive_keys = get_sensitive_leaf_keys()
    safe = deep_mask_config(cfg, sensitive_keys)

    if args.json:
        print_json(safe)
        return

    print(f"平台: {args.name}")
    for k, v in safe.items():
        if isinstance(v, dict):
            print(f"  {k}:")
            for sk, sv in v.items():
                print(f"    {sk}: {sv}")
        else:
            print(f"  {k}: {v}")


def handle_platform_register(args):
    return asyncio.run(_async_register(args))


def handle_platform_unregister(args):
    return asyncio.run(_async_unregister(args))


async def _async_register(args):
    manager = await create_manager()
    try:
        control_class, publish_type_enum = resolve_platform_class(args.name)
        await manager.register_platform(
            platform_name=args.name,
            platform_class=control_class,
            user_data_dir=f"{args.name}_data",
        )
        print(f"平台 '{args.name}' 注册成功。")
    except Exception as e:
        print(f"注册平台失败: {e}")
        return 1
    finally:
        await close_manager(manager)


async def _async_unregister(args):
    manager = await create_manager()
    try:
        success = await manager.unregister_platform(args.name)
        if success:
            print(f"平台 '{args.name}' 已注销。")
        else:
            print(f"平台 '{args.name}' 未找到。")
            return 1
    except Exception as e:
        print(f"注销平台失败: {e}")
        return 1
    finally:
        await close_manager(manager)
