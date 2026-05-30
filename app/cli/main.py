#!/usr/bin/env python3
"""
ai-blogger CLI — AI 多平台自媒体自动运营系统命令行界面

用法:
    ai-blogger --help
    ai-blogger run [--platform ...] [--interval] [--mode]
    ai-blogger platform list|info|register|unregister
    ai-blogger monitor start|stop|status
    ai-blogger publish <name|all> [--title] [--body] [--file]
    ai-blogger prompt list|show|edit|history|rollback|diff
    ai-blogger config show|get
    ai-blogger status
    ai-blogger log [--lines] [--level]
"""

import argparse
import sys
import asyncio

COMMAND_MODULES = {
    "run": "app.cli.commands.run",
    "platform": "app.cli.commands.platform",
    "monitor": "app.cli.commands.monitor",
    "publish": "app.cli.commands.publish",
    "prompt": "app.cli.commands.prompt",
    "config": "app.cli.commands.config",
    "status": "app.cli.commands.status",
    "log": "app.cli.commands.log",
}


def main():
    subparsers = parser.add_subparsers(dest="command", required=True)

    for cmd_name, module_path in COMMAND_MODULES.items():
        if cmd_name == "repl":
            continue
        module = __import__(module_path, fromlist=["register_subparser"])
        module.register_subparser(subparsers)

    args = parser.parse_args()

    if args.command == "repl":
        from app.cli.repl import main as repl_main
        asyncio.run(repl_main())
    if hasattr(args, "func"):
        result = args.func(args)
        if isinstance(result, int) and result != 0:
            sys.exit(result)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
