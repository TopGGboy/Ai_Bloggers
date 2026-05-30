import argparse
import time
from pathlib import Path

from app.core.config_manager import config


def register_subparser(subparsers: argparse._SubParsersAction):
    parser = subparsers.add_parser("log", help="查看最近日志")
    parser.add_argument("--lines", "-n", type=int, default=50, help="显示行数（默认 50）")
    parser.add_argument(
        "--level", "-l",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="按级别过滤",
    )
    parser.add_argument("--follow", "-f", action="store_true", help="持续跟踪日志")
    parser.set_defaults(func=handle_log)


def handle_log(args):
    log_dir = Path(config.logfile_path)
    log_file = log_dir / "app.log"

    if not log_file.exists():
        print(f"日志文件不存在: {log_file}")
        return 1

    lines = _read_tail(log_file, args.lines)

    if args.level:
        level_tag = f" - {args.level.upper()} - "
        lines = [l for l in lines if level_tag in l]

    for line in lines:
        print(line.rstrip())

    if args.follow:
        _follow_log(log_file)


def _read_tail(filepath: Path, n: int) -> list:
    """高效读取文件尾部 n 行"""
    with open(filepath, "r", encoding="utf-8") as f:
        all_lines = f.readlines()
    return all_lines[-n:]


def _follow_log(filepath: Path):
    """类似 tail -f 的持续跟踪"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            f.seek(0, 2)
            while True:
                line = f.readline()
                if line:
                    print(line.rstrip())
                else:
                    time.sleep(0.5)
    except KeyboardInterrupt:
        pass
