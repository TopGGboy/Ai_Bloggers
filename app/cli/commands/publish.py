import argparse
import asyncio
import json
from pathlib import Path
from typing import Any, Dict, Optional

from app.cli.utils.helper import (
    create_manager,
    close_manager,
    resolve_platform_class,
)


def register_subparser(subparsers: argparse._SubParsersAction):
    parser = subparsers.add_parser("publish", help="发布内容到平台")
    parser.add_argument("name", help="平台名称（或 all 发布到所有平台）")
    parser.add_argument("--title", "-t", help="内容标题")
    parser.add_argument("--body", "-b", help="内容正文")
    parser.add_argument("--file", "-f", help="从文件读取内容（支持 .txt / .md / .json）")
    parser.set_defaults(func=handle_publish)


def handle_publish(args):
    return asyncio.run(_async_publish(args))


async def _async_publish(args):
    content = _build_content(args)
    if content is None:
        print("错误: 未提供内容。使用 --title/--body 或 --file。")
        return 1

    manager = await create_manager()
    try:
        if args.name == "all":
            results = await manager.publish_to_all(content)
            for platform, success in results.items():
                status = "✓" if success else "✗"
                print(f"  {platform:<12} {status}")
            if not all(results.values()):
                return 1
        else:
            resolve_platform_class(args.name)  # 验证平台名
            if not manager.is_platform_registered(args.name):
                control_class, publish_type_enum = resolve_platform_class(args.name)
                await manager.register_platform(
                    platform_name=args.name,
                    platform_class=control_class,
                    user_data_dir=f"{args.name}_data",
                )
            success = await manager.publish_to_platform(args.name, content)
            if success:
                print(f"发布到 '{args.name}' 成功。")
            else:
                print(f"发布到 '{args.name}' 失败。")
                return 1
    except ValueError as e:
        print(f"错误: {e}")
        return 1
    except Exception as e:
        print(f"发布失败: {e}")
        return 1
    finally:
        await close_manager(manager)


def _build_content(args) -> Optional[Dict[str, Any]]:
    """从命令行参数构建内容字典"""
    if args.file:
        path = Path(args.file)
        if not path.exists():
            print(f"文件不存在: {args.file}")
            return None
        raw = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            return json.loads(raw)
        return {"content": raw, "title": args.title or path.stem}

    if args.body:
        return {"content": args.body, "title": args.title or ""}

    return None
