import argparse
import copy

from app.core.config_manager import config
from app.cli.utils.helper import (
    print_json,
    deep_mask_config,
    get_sensitive_leaf_keys,
    mask_sensitive,
)


def register_subparser(subparsers: argparse._SubParsersAction):
    parser = subparsers.add_parser("config", help="查看系统配置")
    sub = parser.add_subparsers(dest="config_action", required=True)

    # config show
    p_show = sub.add_parser("show", help="显示完整配置（敏感信息脱敏）")
    p_show.add_argument("--json", action="store_true", help="JSON 格式输出")
    p_show.set_defaults(func=handle_config_show)

    # config get
    p_get = sub.add_parser("get", help="按路径获取配置值，如 app.log_level")
    p_get.add_argument("key", help="配置键路径（点号分隔）")
    p_get.set_defaults(func=handle_config_get)


def handle_config_show(args):
    safe = deep_mask_config(config._config, get_sensitive_leaf_keys())
    if args.json:
        print_json(safe)
        return
    _print_nested(safe)


def handle_config_get(args):
    value = config.get(args.key)
    if value is None:
        print(f"未找到配置项: {args.key}")
        return 1

    leaf_key = args.key.split(".")[-1]
    sensitive_keys = get_sensitive_leaf_keys()
    if leaf_key in sensitive_keys and isinstance(value, str) and value:
        print(f"{args.key}: {mask_sensitive(value)}")
    else:
        print(f"{args.key}: {value}")


def _print_nested(data, indent=0):
    """递归打印嵌套字典"""
    prefix = "  " * indent
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                print(f"{prefix}{k}:")
                _print_nested(v, indent + 1)
            else:
                print(f"{prefix}{k}: {v}")
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                _print_nested(item, indent)
            else:
                print(f"{prefix}- {item}")
