import argparse
from pathlib import Path

from app.core.PromptManager import get_prompt_manager
from app.cli.utils.helper import print_json


def register_subparser(subparsers: argparse._SubParsersAction):
    parser = subparsers.add_parser("prompt", help="管理提示词模板")
    sub = parser.add_subparsers(dest="prompt_action", required=True)

    # prompt list
    p_list = sub.add_parser("list", help="列出所有提示词")
    p_list.add_argument("--platform", "-p", help="按平台过滤 (zhihu/weibo)")
    p_list.set_defaults(func=handle_prompt_list)

    # prompt show
    p_show = sub.add_parser("show", help="查看提示词完整内容")
    p_show.add_argument("id", help="提示词 ID (如 zhihu_answer)")
    p_show.set_defaults(func=handle_prompt_show)

    # prompt edit
    p_edit = sub.add_parser("edit", help="从文件编辑提示词")
    p_edit.add_argument("id", help="提示词 ID")
    p_edit.add_argument("file", help="包含新内容的文件路径")
    p_edit.add_argument("--reason", "-r", default="CLI 编辑", help="变更原因")
    p_edit.set_defaults(func=handle_prompt_edit)

    # prompt history
    p_hist = sub.add_parser("history", help="查看版本历史")
    p_hist.add_argument("id", help="提示词 ID")
    p_hist.add_argument("--json", action="store_true", help="JSON 格式输出")
    p_hist.set_defaults(func=handle_prompt_history)

    # prompt rollback
    p_rb = sub.add_parser("rollback", help="回滚到指定版本")
    p_rb.add_argument("id", help="提示词 ID")
    p_rb.add_argument("version", help="版本 ID (如 v_20260513_100000)")
    p_rb.set_defaults(func=handle_prompt_rollback)

    # prompt diff
    p_diff = sub.add_parser("diff", help="比较两个版本差异")
    p_diff.add_argument("id", help="提示词 ID")
    p_diff.add_argument("v1", help="版本一")
    p_diff.add_argument("v2", help="版本二")
    p_diff.set_defaults(func=handle_prompt_diff)


def handle_prompt_list(args):
    pm = get_prompt_manager()
    prompts = pm.list_prompts(filter_platform=args.platform)

    if not prompts:
        print("未找到提示词。")
        return

    print(f"{'ID':<22} {'名称':<28} {'平台':<10} {'版本':<12}")
    print("-" * 72)
    for p in prompts:
        print(f"{p['id']:<22} {p.get('name', ''):<28} {p.get('platform', ''):<10} {p.get('active_version', ''):<12}")


def handle_prompt_show(args):
    pm = get_prompt_manager()
    try:
        prompt = pm.get_prompt(args.id)
    except FileNotFoundError as e:
        print(f"提示词未找到: {e}")
        return 1

    print(f"ID:      {prompt.id}")
    print(f"名称:    {prompt.name}")
    print(f"版本:    {prompt.version}")
    print(f"更新:    {prompt.updated_at}")
    print("--- 内容 ---")
    print(prompt.content)


def handle_prompt_edit(args):
    path = Path(args.file)
    if not path.exists():
        print(f"文件不存在: {args.file}")
        return 1

    new_content = path.read_text(encoding="utf-8")
    pm = get_prompt_manager()
    try:
        updated = pm.update_prompt(
            prompt_id=args.id,
            content=new_content,
            change_reason=args.reason,
            source="cli_edit",
        )
        print(f"提示词 '{args.id}' 已更新至版本 {updated.version}。")
    except Exception as e:
        print(f"更新提示词失败: {e}")
        return 1


def handle_prompt_history(args):
    pm = get_prompt_manager()
    try:
        history = pm.get_history(args.id)
    except Exception as e:
        print(f"获取历史失败: {e}")
        return 1

    if args.json:
        print_json([_record_to_dict(r) for r in history])
        return

    if not history:
        print(f"提示词 '{args.id}' 暂无历史记录。")
        return

    print(f"{'版本 ID':<24} {'时间戳':<22} {'类型':<14} {'语义版本':<14} {'原因'}")
    print("-" * 100)
    for r in history:
        print(f"{r.version_id:<24} {r.timestamp:<22} "
              f"{r.change_type:<14} {r.version:<14} {r.change_reason}")


def _record_to_dict(r) -> dict:
    """将 VersionRecord 转为字典"""
    return {
        "version_id": r.version_id,
        "timestamp": r.timestamp,
        "version": r.version,
        "change_type": r.change_type,
        "change_reason": r.change_reason,
        "source": r.source,
    }


def handle_prompt_rollback(args):
    pm = get_prompt_manager()
    try:
        updated = pm.rollback(args.id, args.version)
        print(f"提示词 '{args.id}' 已回滚至 {args.version}（当前版本: {updated.version}）。")
    except Exception as e:
        print(f"回滚失败: {e}")
        return 1


def handle_prompt_diff(args):
    pm = get_prompt_manager()
    try:
        result = pm.compare_versions(args.id, args.v1, args.v2)
    except Exception as e:
        print(f"比较失败: {e}")
        return 1

    if result is None:
        print(f"版本未找到: {args.v1} / {args.v2}")
        return 1

    print(f"差异: {result.changes_summary}")
    print()
    if result.deletions:
        print("--- 删除的行:")
        for line in result.deletions:
            print(f"  - {line}")
    if result.additions:
        print("+++ 新增的行:")
        for line in result.additions:
            print(f"  + {line}")
