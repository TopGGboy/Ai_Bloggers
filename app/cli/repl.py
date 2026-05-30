"""
AI-Blogger 交互式命令行界面（REPL）

用户可以在持续的黑窗口中输入各种命令来控制系统。
"""

import asyncio
import sys
import shlex
from typing import Optional, Dict, Any

from app.cli.utils.helper import (
    create_manager,
    close_manager,
    resolve_platform_class,
    parse_platform_mode,
    get_publish_type_value,
    get_known_platforms,
    print_json,
    mask_sensitive,
    deep_mask_config,
    get_sensitive_leaf_keys,
)
from app.core.config_manager import config
from app.core.PromptManager import get_prompt_manager
from app.core.MultiPlatformManager import MultiPlatformManager


class AiBloggerREPL:
    """AI-Blogger 交互式命令行界面（REPL）"""

    def __init__(self):
        self.running = True
        self.manager: Optional[MultiPlatformManager] = None
        self.command_history = []
        self.history_index = -1

    async def _initialize(self):
        """初始化管理器"""
        try:
            self.manager = await create_manager()
            print("✓ 系统初始化完成\n")
        except Exception as e:
            print(f"✗ 初始化失败: {e}\n")
            self.manager = None

    async def _cleanup(self):
        """清理资源"""
        if self.manager:
            await close_manager(self.manager)
            print("\n✓ 系统已安全关闭")

    def _get_completions(self, text: str, state: int) -> Optional[str]:
        """命令自动补全（简化版）"""
        commands = [
            'help', 'exit', 'quit', 'clear',
            'status', 'config', 'log',
            'platform', 'monitor', 'publish', 'prompt', 'run'
        ]

        if state == 0:
            self.matches = [cmd for cmd in commands if cmd.startswith(text)]

        if state < len(self.matches):
            return self.matches[state]
        return None

    def _print_banner(self):
        """打印欢迎横幅"""
        banner = """
                ╔════════════════════════════════════════════════════════════════╗
                ║                    AI-Blogger 交互式控制台                      ║
                ║              AI 多平台自媒体自动运营系统                        ║
                ╚════════════════════════════════════════════════════════════════╝

                输入 'help' 查看可用命令，输入 'exit' 或 'quit' 退出。
                """
        print(banner)

    def _print_prompt(self):
        """打印命令提示符"""
        return "ai-blogger> "

    async def cmd_help(self, args: list) -> Optional[int]:
        """显示帮助信息"""
        if not args:
            print(
                """
                可用命令:
                  help                    显示此帮助信息
                  exit / quit             退出交互式控制台
                  clear                   清屏
                
                  status                  查看系统整体状态
                  config show             显示完整配置（敏感信息脱敏）
                  config get <key>        按路径获取配置值，如 app.log_level
                
                  platform list           列出所有已配置平台
                  platform info <name>    查看平台详细信息
                  platform register <name> 注册平台（需浏览器环境）
                  platform unregister <name> 注销平台
                
                
                  monitor start          启动平台监控（阻塞直到 Ctrl+C）
                    --platform_name      监控的平台（默认: zhihu weibo）
                    --mode               运行模式（monitor_only/publish_only/monitor_and_publish）
                    --publish_type       发布类型（article/essay/other）
                  monitor stop <name>     停止平台监控
                  monitor status [name]   查看监控运行状态
                
                  publish <name|all>      发布内容到平台
                    --title <title>       内容标题
                    --body <body>         内容正文
                    --file <path>         从文件读取内容（支持 .txt / .md / .json）
                
                  prompt list             列出所有提示词
                  prompt show <id>        查看提示词完整内容
                  prompt edit <id> <file> 从文件编辑提示词
                  prompt history <id>     查看版本历史
                  prompt rollback <id> <version> 回滚到指定版本
                  prompt diff <id> <v1> <v2> 比较两个版本差异
                
                  run                     启动主监控循环（阻塞直到 Ctrl+C）
                    --platform <name>     要运行的平台（默认: zhihu weibo）
                    --interval <seconds>  监控检查间隔秒数（默认: 600）
                    --mode <mode>         运行模式（monitor_only/publish_only/monitor_and_publish）
                
                  log                     查看最近日志
                    --lines <n>           显示行数（默认 50）
                    --level <level>       按级别过滤（DEBUG/INFO/WARNING/ERROR/CRITICAL）
                
                提示:
                  - 使用 Tab 键可以自动补全命令
                  - 使用上下箭头可以浏览命令历史
                  - 输入命令名 --help 可以查看该命令的详细帮助
                """
            )
        else:
            # 显示特定命令的帮助
            cmd = args[0].lower()
            help_texts = {
                'platform': """
platform 命令:
  platform list           列出所有已配置平台
  platform info <name>    查看平台详细信息
  platform register <name> 注册平台（需浏览器环境）
  platform unregister <name> 注销平台

示例:
  platform list
  platform info zhihu
  platform register weibo
  platform unregister zhihu
""",
                'monitor': """
monitor 命令:
  monitor start          启动平台监控（阻塞直到 Ctrl+C）
    --platform_name      监控的平台（默认: zhihu weibo）
    --mode               运行模式（monitor_only/publish_only/monitor_and_publish）
    --publish_type       发布类型（article/essay/other）
    --interval <seconds>  检查间隔秒数（默认: 600）
  monitor stop <name>     停止平台监控
  monitor status [name]   查看监控运行状态

示例:
  monitor start
  monitor start --platform_name zhihu
  monitor start --platform_name zhihu weibo --mode monitor_only
  monitor start --platform_name zhihu --publish_type article
  monitor stop zhihu
  monitor status
  monitor status zhihu
""",
                'publish': """
publish 命令:
  publish <name|all>      发布内容到平台
    --title <title>       内容标题
    --body <body>         内容正文
    --file <path>         从文件读取内容（支持 .txt / .md / .json）

示例:
  publish zhihu --title "测试标题" --body "测试内容"
  publish all --file content.md
  publish weibo --file post.json
""",
                'prompt': """
prompt 命令:
  prompt list             列出所有提示词
    --platform <name>     按平台过滤 (zhihu/weibo)
  prompt show <id>        查看提示词完整内容
  prompt edit <id> <file> 从文件编辑提示词
    --reason <text>       变更原因（默认: CLI 编辑）
  prompt history <id>     查看版本历史
    --json                JSON 格式输出
  prompt rollback <id> <version> 回滚到指定版本
  prompt diff <id> <v1> <v2> 比较两个版本差异

示例:
  prompt list
  prompt list --platform zhihu
  prompt show zhihu_answer
  prompt edit zhihu_answer new_prompt.txt
  prompt history zhihu_answer
  prompt rollback zhihu_answer v_20260513_100000
  prompt diff zhihu_answer v_20260513_100000 v_20260514_120000
""",
                'run': """
run 命令:
  run                     启动主监控循环（阻塞直到 Ctrl+C）
    --platform <name>     要运行的平台（默认: zhihu weibo）
    --interval <seconds>  监控检查间隔秒数（默认: 600）
    --mode <mode>         运行模式
                          - monitor_only: 仅监控
                          - publish_only: 仅发布
                          - monitor_and_publish: 监控+发布（默认）

示例:
  run
  run --platform zhihu
  run --platform zhihu weibo --interval 300
  run --mode monitor_only
""",
                'log': """
log 命令:
  log                     查看最近日志
    --lines <n>           显示行数（默认 50）
    --level <level>       按级别过滤（DEBUG/INFO/WARNING/ERROR/CRITICAL）
    --follow              持续跟踪日志（类似 tail -f）

示例:
  log
  log --lines 100
  log --level ERROR
  log --follow
""",
            }
            print(help_texts.get(cmd, f"没有找到命令 '{cmd}' 的帮助信息\n"))
        return None

    async def cmd_exit(self, args: list) -> int:
        """退出交互式控制台"""
        self.running = False
        print("再见！")
        return 0

    async def cmd_clear(self, args: list) -> None:
        """清屏"""
        print("\033[2J\033[H", end="")

    async def cmd_status(self, args: list) -> None:
        """查看系统整体状态"""
        pm = get_prompt_manager()
        prompts = pm.list_prompts()
        known_platforms = get_known_platforms()

        resource_stats = {}
        try:
            if self.manager:
                resource_stats = self.manager.get_resource_stats()
                platform_info = self.manager.get_all_platforms_info()
                resource_stats['platforms_info'] = platform_info
            else:
                resource_stats = {
                    "platform_count": 0,
                    "active_monitors": 0,
                    "task_stats": {"total_tasks": 0, "success_tasks": 0, "failed_tasks": 0},
                    "platforms_info": [],
                }
        except Exception:
            resource_stats = {
                "platform_count": 0,
                "active_monitors": 0,
                "task_stats": {"total_tasks": 0, "success_tasks": 0, "failed_tasks": 0},
                "platforms_info": [],
            }

        print("=== AI-Blogger 系统状态 ===")
        print()
        print(f"配置的平台:    {', '.join(known_platforms.keys()) or '无'}")
        print(f"注册的提示词:  {len(prompts)}")
        print(f"活跃监控数:    {resource_stats.get('active_monitors', 0)}")
        print(f"平台实例数:    {resource_stats.get('platform_count', 0)}")
        ts = resource_stats.get("task_stats", {})
        print(f"任务统计:      {ts.get('total_tasks', 0)} 总 / "
              f"{ts.get('success_tasks', 0)} 成功 / "
              f"{ts.get('failed_tasks', 0)} 失败\n")
        return None

    async def cmd_config(self, args: list) -> Optional[int]:
        """查看系统配置"""
        if not args:
            print("用法: config show | config get <key>\n")
            return 1

        action = args[0].lower()

        if action == "show":
            safe = deep_mask_config(config._config, get_sensitive_leaf_keys())
            self._print_nested(safe)
            print()
        elif action == "get":
            if len(args) < 2:
                print("用法: config get <key>\n")
                return 1
            key = args[1]
            value = config.get(key)
            if value is None:
                print(f"未找到配置项: {key}\n")
                return 1

            leaf_key = key.split(".")[-1]
            sensitive_keys = get_sensitive_leaf_keys()
            if leaf_key in sensitive_keys and isinstance(value, str) and value:
                print(f"{key}: {mask_sensitive(value)}\n")
            else:
                print(f"{key}: {value}\n")
        else:
            print(f"未知操作: {action}\n")
            return 1

        return None

    async def cmd_log(self, args: list) -> Optional[int]:
        """查看最近日志"""
        import time

        lines = 50
        level = None
        follow = False

        i = 0
        while i < len(args):
            if args[i] in ['--lines', '-n']:
                if i + 1 < len(args):
                    lines = int(args[i + 1])
                    i += 2
                else:
                    print("--lines 需要参数\n")
                    return 1
            elif args[i] in ['--level', '-l']:
                if i + 1 < len(args):
                    level = args[i + 1].upper()
                    i += 2
                else:
                    print("--level 需要参数\n")
                    return 1
            elif args[i] == '--follow':
                follow = True
                i += 1
            else:
                i += 1

        log_dir = Path(config.logfile_path)
        log_file = log_dir / "app.log"

        if not log_file.exists():
            print(f"日志文件不存在: {log_file}\n")
            return 1

        log_lines = self._read_tail(log_file, lines)

        if level:
            level_tag = f" - {level.upper()} - "
            log_lines = [l for l in log_lines if level_tag in l]

        for line in log_lines:
            print(line.rstrip())

        if follow:
            print("\n持续跟踪日志中... (按 Ctrl+C 停止)")
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    f.seek(0, 2)
                    while True:
                        line = f.readline()
                        if line:
                            print(line.rstrip())
                        else:
                            await asyncio.sleep(0.5)
            except KeyboardInterrupt:
                print("\n")

        return None

    async def cmd_platform(self, args: list) -> Optional[int]:
        """管理平台"""
        if not args:
            print("用法: platform list | info <name> | register <name> | unregister <name>\n")
            return 1

        action = args[0].lower()

        if action == "list":
            platforms = get_known_platforms()
            if not platforms:
                print("未配置任何平台。\n")
                return None

            print(f"{'平台':<12} {'登录方式':<18} {'检查间隔':<14}")
            print("-" * 44)

            for name, cfg in platforms.items():
                login_type = cfg.get("login_type", "N/A")
                interval = f"{cfg.get('check_interval', 'N/A')}s"
                print(f"{name:<12} {login_type:<18} {interval:<14}")
            print()

        elif action == "info":
            if len(args) < 2:
                print("用法: platform info <name>\n")
                return 1

            name = args[1]
            platforms = get_known_platforms()
            if name not in platforms:
                print(f"配置中未找到平台 '{name}'。\n")
                return 1

            cfg = platforms[name]
            sensitive_keys = get_sensitive_leaf_keys()
            safe = deep_mask_config(cfg, sensitive_keys)

            print(f"平台: {name}")
            for k, v in safe.items():
                if isinstance(v, dict):
                    print(f"  {k}:")
                    for sk, sv in v.items():
                        print(f"    {sk}: {sv}")
                else:
                    print(f"  {k}: {v}")
            print()
        elif action == "register":
            if len(args) < 2:
                print("用法: platform register <name>\n")
                return 1

            name = args[1]
            if not self.manager:
                print("错误: 管理器未初始化\n")
                return 1

            try:
                control_class, publish_type_enum = resolve_platform_class(name)
                publish_type_value = get_publish_type_value(name, publish_type_enum)
                await self.manager.register_platform(
                    platform_name=name,
                    platform_class=control_class,
                    user_data_dir=f"{name}_data",
                    mode=parse_platform_mode("monitor_and_publish"),
                    publish_type=publish_type_value,
                )
                print(f"平台 '{name}' 注册成功。\n")
            except Exception as e:
                print(f"注册平台失败: {e}\n")
                return 1

        elif action == "unregister":
            if len(args) < 2:
                print("用法: platform unregister <name>\n")
                return 1

            name = args[1]
            if not self.manager:
                print("错误: 管理器未初始化\n")
                return 1

            try:
                success = await self.manager.unregister_platform(name)
                if success:
                    print(f"平台 '{name}' 已注销。\n")
                else:
                    print(f"平台 '{name}' 未找到。\n")
                    return 1
            except Exception as e:
                print(f"注销平台失败: {e}\n")
                return 1

        else:
            print(f"未知操作: {action}\n")
            return 1

        return None

    async def cmd_monitor(self, args: list) -> Optional[int]:
        """控制平台监控"""
        if not args:
            print("用法: monitor start <name> | stop <name> | status [name]\n")
            return 1

        action = args[0].lower()

        if action == "start":
            platforms = ["zhihu", "weibo"]
            mode = "monitor_and_publish"
            publish_type = None
            interval = 600

            i = 1
            while i < len(args):
                if args[i] == '--platform_name':
                    if i + 1 < len(args):
                        platforms = args[i + 1:]
                        # 找到下一个参数的起始位置
                        j = i + 1
                        while j < len(args) and not args[j].startswith('--'):
                            j += 1
                        platforms = args[i + 1:j]
                        i = j
                    else:
                        print("--platform_name 需要参数\n")
                        return 1
                elif args[i] == '--mode':
                    if i + 1 < len(args):
                        mode = args[i + 1]
                        i += 2
                    else:
                        print("--mode 需要参数\n")
                        return 1
                elif args[i] == '--publish_type':
                    if i + 1 < len(args):
                        publish_type = args[i + 1]
                        i += 2
                    else:
                        print("--publish_type 需要参数\n")
                        return 1
                elif args[i] in ['--interval', '-i']:
                    if i + 1 < len(args):
                        interval = int(args[i + 1])
                        i += 2
                    else:
                        print("--interval 需要参数\n")
                        return 1
                else:
                    i += 1

            if not self.manager:
                print("错误: 管理器未初始化\n")
                return 1

            try:
                parsed_mode = parse_platform_mode(mode)

                for platform_name in platforms:
                    control_class, publish_type_enum = resolve_platform_class(platform_name)
                    if publish_type:
                        publish_value = self._resolve_publish_type(platform_name, publish_type, publish_type_enum)
                    else:
                        publish_value = get_publish_type_value(platform_name, publish_type_enum)

                    if not self.manager.is_platform_registered(platform_name):
                        await self.manager.register_platform(
                            platform_name=platform_name,
                            platform_class=control_class,
                            user_data_dir=f"{platform_name}_data",
                            mode=parsed_mode,
                            publish_type=publish_value,
                        )
                intervals = {name: interval for name in platforms}
                await self.manager.start_all_monitors(intervals)

                platform_list = ", ".join(platforms)
                print(f"监控已启动: [{platform_list}] | 模式: {mode} | 间隔: {interval}s")
                print("按 Ctrl+C 停止。")

                while True:
                    await asyncio.sleep(1)

            except KeyboardInterrupt:
                print("\n正在停止监控...\n")
            except Exception as e:
                print(f"启动监控失败: {e}\n")
                return 1

        elif action == "stop":
            if len(args) < 2:
                print("用法: monitor stop <name>\n")
                return 1

            name = args[1]
            if not self.manager:
                print("错误: 管理器未初始化\n")
                return 1

            try:
                success = await self.manager.stop_monitor(name)
                if success:
                    print(f"监控已停止: '{name}'。\n")
                else:
                    print(f"未找到 '{name}' 的运行监控。\n")
                    return 1
            except Exception as e:
                print(f"停止监控失败: {e}\n")
                return 1

        elif action == "status":
            name = args[1] if len(args) > 1 else None

            if not self.manager:
                print("错误: 管理器未初始化\n")
                return 1

            try:
                if name:
                    running = self.manager.get_monitor_status(name)
                    data = {name: running}
                else:
                    running_list = self.manager.list_running_monitors()
                    data = {n: True for n in running_list}

                if not data:
                    print("没有运行中的监控。\n")
                    return None

                for n, running in data.items():
                    status_str = "运行中" if running else "已停止"
                    print(f"  {n:<12} {status_str}")
                print()
            except Exception as e:
                print(f"查看监控状态失败: {e}\n")
                return 1

        else:
            print(f"未知操作: {action}\n")
            return 1

        return None

    async def cmd_publish(self, args: list) -> Optional[int]:
        """发布内容到平台"""
        if not args:
            print("用法: publish <name|all> [--title <title>] [--body <body>] [--file <path>]\n")
            return 1

        name = args[0]
        title = None
        body = None
        file_path = None

        i = 1
        while i < len(args):
            if args[i] in ['--title', '-t']:
                if i + 1 < len(args):
                    title = args[i + 1]
                    i += 2
                else:
                    print("--title 需要参数\n")
                    return 1
            elif args[i] in ['--body', '-b']:
                if i + 1 < len(args):
                    body = args[i + 1]
                    i += 2
                else:
                    print("--body 需要参数\n")
                    return 1
            elif args[i] in ['--file', '-f']:
                if i + 1 < len(args):
                    file_path = args[i + 1]
                    i += 2
                else:
                    print("--file 需要参数\n")
                    return 1
            else:
                i += 1

            content = self._build_content(title, body, file_path)
            if content is None:
                print("错误: 未提供内容。使用 --title/--body 或 --file。\n")
                return 1

            if not self.manager:
                print("错误: 管理器未初始化\n")
                return 1

            try:
                if name == "all":
                    results = await self.manager.publish_to_all(content)
                    for platform, success in results.items():
                        status = "✓" if success else "✗"
                        print(f"  {platform:<12} {status}")
                    print()
                    if not all(results.values()):
                        return 1
                else:
                    resolve_platform_class(name)
                    if not self.manager.is_platform_registered(name):
                        control_class, publish_type_enum = resolve_platform_class(name)
                        await self.manager.register_platform(
                            platform_name=name,
                            platform_class=control_class,
                            user_data_dir=f"{name}_data",
                        )
                    success = await self.manager.publish_to_platform(name, content)
                    if success:
                        print(f"发布到 '{name}' 成功。\n")
                    else:
                        print(f"发布到 '{name}' 失败。\n")
                        return 1
            except ValueError as e:
                print(f"错误: {e}\n")
                return 1
            except Exception as e:
                print(f"发布失败: {e}\n")
                return 1

            return None

    async def cmd_prompt(self, args: list) -> Optional[int]:
        """管理提示词模板"""
        if not args:
            print(
                "用法: prompt list | show <id> | edit <id> <file> | history <id> | rollback <id> <version> | diff <id> <v1> <v2>\n")
            return 1

        action = args[0].lower()
        pm = get_prompt_manager()

        if action == "list":
            platform = None

            i = 1
            while i < len(args):
                if args[i] in ['--platform', '-p']:
                    if i + 1 < len(args):
                        platform = args[i + 1]
                        i += 2
                    else:
                        print("--platform 需要参数\n")
                        return 1
                else:
                    i += 1

            prompts = pm.list_prompts(filter_platform=platform)

            if not prompts:
                print("未找到提示词。\n")
                return None

            print(f"{'ID':<22} {'名称':<28} {'平台':<10} {'版本':<12}")
            print("-" * 72)
            for p in prompts:
                print(
                    f"{p['id']:<22} {p.get('name', ''):<28} {p.get('platform', ''):<10} {p.get('active_version', ''):<12}")
            print()

        elif action == "show":
            if len(args) < 2:
                print("用法: prompt show <id>\n")
                return 1

            prompt_id = args[1]
            try:
                prompt = pm.get_prompt(prompt_id)
            except FileNotFoundError as e:
                print(f"提示词未找到: {e}\n")
                return 1

            print(f"ID:      {prompt.id}")
            print(f"名称:    {prompt.name}")
            print(f"版本:    {prompt.version}")
            print(f"更新:    {prompt.updated_at}")
            print("--- 内容 ---")
            print(prompt.content)
            print()

        elif action == "edit":
            if len(args) < 3:
                print("用法: prompt edit <id> <file> [--reason <reason>]\n")
                return 1

            prompt_id = args[1]
            file_path = args[2]
            reason = "CLI 编辑"

            i = 3
            while i < len(args):
                if args[i] in ['--reason', '-r']:
                    if i + 1 < len(args):
                        reason = args[i + 1]
                        i += 2
                    else:
                        print("--reason 需要参数\n")
                        return 1
                else:
                    i += 1

            path = Path(file_path)
            if not path.exists():
                print(f"文件不存在: {file_path}\n")
                return 1

            new_content = path.read_text(encoding="utf-8")
            try:
                updated = pm.update_prompt(
                    prompt_id=prompt_id,
                    content=new_content,
                    change_reason=reason,
                    source="cli_edit",
                )
                print(f"提示词 '{prompt_id}' 已更新至版本 {updated.version}。\n")
            except Exception as e:
                print(f"更新提示词失败: {e}\n")
                return 1

        elif action == "history":
            if len(args) < 2:
                print("用法: prompt history <id> [--json]\n")
                return 1

            prompt_id = args[1]
            json_output = False

            i = 2
            while i < len(args):
                if args[i] == '--json':
                    json_output = True
                    i += 1
                else:
                    i += 1

            try:
                history = pm.get_history(prompt_id)
            except Exception as e:
                print(f"获取历史失败: {e}\n")
                return 1

            if json_output:
                print_json([self._record_to_dict(r) for r in history])
                print()
                return None

            if not history:
                print(f"提示词 '{prompt_id}' 暂无历史记录。\n")
                return None

            print(f"{'版本 ID':<24} {'时间戳':<22} {'类型':<14} {'语义版本':<14} {'原因'}")
            print("-" * 100)
            for r in history:
                print(f"{r.version_id:<24} {r.timestamp:<22} "
                      f"{r.change_type:<14} {r.version:<14} {r.change_reason}")
            print()

        elif action == "rollback":
            if len(args) < 3:
                print("用法: prompt rollback <id> <version>\n")
                return 1

            prompt_id = args[1]
            version = args[2]

            try:
                updated = pm.rollback(prompt_id, version)
                print(f"提示词 '{prompt_id}' 已回滚至 {version}（当前版本: {updated.version}）。\n")
            except Exception as e:
                print(f"回滚失败: {e}\n")
                return 1

        elif action == "diff":
            if len(args) < 4:
                print("用法: prompt diff <id> <v1> <v2>\n")
                return 1

            prompt_id = args[1]
            v1 = args[2]
            v2 = args[3]

            try:
                result = pm.compare_versions(prompt_id, v1, v2)
            except Exception as e:
                print(f"比较失败: {e}\n")
                return 1

            if result is None:
                print(f"版本未找到: {v1} / {v2}\n")
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
            print()

        else:
            print(f"未知操作: {action}\n")
            return 1

        return None

    async def cmd_run(self, args: list) -> Optional[int]:
        """启动主监控循环"""
        platforms = ["zhihu", "weibo"]
        interval = 600
        mode = "monitor_and_publish"

        i = 0
        while i < len(args):
            if args[i] in ['--platform', '-p']:
                if i + 1 < len(args):
                    platforms = args[i + 1].split(',')
                    i += 2
                else:
                    print("--platform 需要参数\n")
                    return 1
            elif args[i] in ['--interval', '-i']:
                if i + 1 < len(args):
                    interval = int(args[i + 1])
                    i += 2
                else:
                    print("--interval 需要参数\n")
                    return 1
            elif args[i] in ['--mode', '-m']:
                if i + 1 < len(args):
                    mode = args[i + 1]
                    i += 2
                else:
                    print("--mode 需要参数\n")
                    return 1
            else:
                i += 1

        if not self.manager:
            print("错误: 管理器未初始化\n")
            return 1

        try:
            parsed_mode = parse_platform_mode(mode)

            for platform_name in platforms:
                control_class, publish_type_enum = resolve_platform_class(platform_name)
                publish_value = get_publish_type_value(platform_name, publish_type_enum)
                await self.manager.register_platform(
                    platform_name=platform_name,
                    platform_class=control_class,
                    user_data_dir=f"{platform_name}_data",
                    mode=parsed_mode,
                    publish_type=publish_value,
                )

            intervals = {name: interval for name in platforms}
            await self.manager.start_all_monitors(intervals)

            platform_list = ", ".join(platforms)
            print(f"AI-Blogger 监控已启动 — 平台: [{platform_list}] | "
                  f"间隔: {interval}s | 模式: {mode}")
            print("按 Ctrl+C 停止。")

            while True:
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            print("\n正在关闭…")
        except Exception as e:
            print(f"启动失败: {e}\n")
            return 1

        return None

    def _build_content(self, title: Optional[str], body: Optional[str], file_path: Optional[str]) -> Optional[
        Dict[str, Any]]:
        """从参数构建内容字典"""
        if file_path:
            path = Path(file_path)
            if not path.exists():
                print(f"文件不存在: {file_path}")
                return None
            import json
            raw = path.read_text(encoding="utf-8")
            if path.suffix.lower() == ".json":
                return json.loads(raw)
            return {"content": raw, "title": title or path.stem}

        if body:
            return {"content": body, "title": title or ""}

        return None

    def _print_nested(self, data, indent=0):
        """递归打印嵌套字典"""
        prefix = "  " * indent
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, (dict, list)):
                    print(f"{prefix}{k}:")
                    self._print_nested(v, indent + 1)
                else:
                    print(f"{prefix}{k}: {v}")
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, (dict, list)):
                    self._print_nested(item, indent)
                else:
                    print(f"{prefix}- {item}")

    def _read_tail(self, filepath, n: int) -> list:
        """高效读取文件尾部 n 行"""
        with open(filepath, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
        return all_lines[-n:]

    def _resolve_publish_type(self, platform_name: str, publish_type: str, publish_type_enum: type):
        """将用户输入的发布类型映射到对应平台的枚举值"""
        mapping = {
            "zhihu": {
                "article": "ARTICLE",
                "answer": "ANSWER",
            },
            "weibo": {
                "essay": "ESSAY",
            },
        }
        platform_mapping = mapping.get(platform_name, {})
        enum_key = platform_mapping.get(publish_type.lower())
        if enum_key and hasattr(publish_type_enum, enum_key):
            return getattr(publish_type_enum, enum_key)
        return get_publish_type_value(platform_name, publish_type_enum)

    def _resolve_publish_type(self, platform_name: str, publish_type: str, publish_type_enum: type):
        """将用户输入的发布类型映射到对应平台的枚举值"""
        mapping = {
            "zhihu": {
                "article": "ARTICLE",
                "answer": "ANSWER",
            },
            "weibo": {
                "essay": "ESSAY",
            },
        }
        platform_mapping = mapping.get(platform_name, {})
        enum_key = platform_mapping.get(publish_type.lower())
        if enum_key and hasattr(publish_type_enum, enum_key):
            return getattr(publish_type_enum, enum_key)
        return get_publish_type_value(platform_name, publish_type_enum)

    def _resolve_publish_type(self, platform_name: str, publish_type: str, publish_type_enum: type):
        """将用户输入的发布类型映射到对应平台的枚举值"""
        mapping = {
            "zhihu": {
                "article": "ARTICLE",
                "answer": "ANSWER",
            },
            "weibo": {
                "essay": "ESSAY",
            },
        }
        platform_mapping = mapping.get(platform_name, {})
        enum_key = platform_mapping.get(publish_type.lower())
        if enum_key and hasattr(publish_type_enum, enum_key):
            return getattr(publish_type_enum, enum_key)
        return get_publish_type_value(platform_name, publish_type_enum)

    def _record_to_dict(self, r) -> dict:
        """将 VersionRecord 转为字典"""
        return {
            "version_id": r.version_id,
            "timestamp": r.timestamp,
            "version": r.version,
            "change_type": r.change_type,
            "change_reason": r.change_reason,
            "source": r.source,
        }

    async def _execute_command(self, cmd_line: str):
        """执行用户输入的命令"""
        cmd_line = cmd_line.strip()
        if not cmd_line:
            return

        # 添加到历史记录
        self.command_history.append(cmd_line)
        self.history_index = len(self.command_history)

        try:
            parts = shlex.split(cmd_line)
            if not parts:
                return

            command = parts[0].lower()
            args = parts[1:]

            # 命令路由
            handlers = {
                'help': self.cmd_help,
                'exit': self.cmd_exit,
                'quit': self.cmd_exit,
                'clear': self.cmd_clear,
                'status': self.cmd_status,
                'config': self.cmd_config,
                'log': self.cmd_log,
                'platform': self.cmd_platform,
                'monitor': self.cmd_monitor,
                'publish': self.cmd_publish,
                'prompt': self.cmd_prompt,
                'run': self.cmd_run,
            }

            handler = handlers.get(command)  # 获取命令处理函数
            if handler:
                result = await handler(args)
                if isinstance(result, int) and result != 0:
                    print(f"命令执行失败 (退出码: {result})")
            else:
                print(f"未知命令: {command}")
                print("输入 'help' 查看可用命令\n")

        except ValueError as e:
            print(f"参数错误: {e}\n")
        except Exception as e:
            print(f"执行错误: {e}\n")

    async def run(self):
        """运行交互式循环"""
        self._print_banner()
        await self._initialize()

        try:
            while self.running:
                try:
                    cmd_input = input(self._print_prompt())
                    await self._execute_command(cmd_input)
                except EOFError:
                    print("\n")
                    self.running = False
                except KeyboardInterrupt:
                    print("\n输入 'exit' 或 'quit' 退出。\n")
        finally:
            await self._cleanup()


async def main():
    """主入口"""
    repl = AiBloggerREPL()
    await repl.run()


if __name__ == '__main__':
    asyncio.run(main())
