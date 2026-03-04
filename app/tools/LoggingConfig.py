import logging
import sys
import inspect
from pathlib import Path
from typing import Optional, Dict, Any
from logging.handlers import RotatingFileHandler
import threading

# 兼容Windows系统的ANSI颜色（如果需要）
try:
    import colorama

    colorama.init(autoreset=True)
except ImportError:
    colorama = None


class LoggingConfig:
    """
    日志配置单例类，统一管理文件/控制台日志输出，支持：
    1. 单例模式（线程安全）
    2. 控制台彩色日志（兼容非终端环境）
    3. 自动获取调用者名称
    4. 日志文件轮转（避免文件过大）
    5. 健壮的异常处理和边界场景兼容
    """
    # 单例实例（线程安全）
    _instance: Optional['LoggingConfig'] = None
    _lock = threading.Lock()
    _initialized: bool = False

    # 默认配置
    DEFAULT_LOG_FILENAME: str = "app.log"
    DEFAULT_LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
    DEFAULT_LOG_LEVEL: int = logging.INFO
    # 日志轮转配置：单个文件最大50MB，保留5个备份
    MAX_LOG_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB
    BACKUP_COUNT: int = 5

    def __new__(cls, *args, **kwargs):
        """线程安全的单例模式实现"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
            self,
            log_file_path: Optional[Path] = None,
            log_filename: str = DEFAULT_LOG_FILENAME,
            log_level: int = DEFAULT_LOG_LEVEL,
            max_file_size: int = MAX_LOG_FILE_SIZE,
            backup_count: int = BACKUP_COUNT
    ):
        """
        初始化日志系统（仅首次调用生效）

        :param log_file_path: 日志文件存储目录，默认当前工作目录
        :param log_filename: 日志文件名，默认 app.log
        :param log_level: 日志级别，默认 INFO
        :param max_file_size: 单个日志文件最大字节数，默认50MB
        :param backup_count: 日志备份文件数量，默认5个
        """
        # 防止重复初始化（单例核心）
        if hasattr(self, '_initialized') and self._initialized:
            return

        # 基础配置初始化
        self.log_file_path = log_file_path or Path.cwd()
        self.log_filename = log_filename
        self.log_level = log_level
        self.max_file_size = max_file_size
        self.backup_count = backup_count

        # 确保日志目录存在（带异常处理）
        self._ensure_log_directory_exists()

        # 构建完整日志文件路径
        self.log_filepath: Path = self._build_log_filepath()

        # 获取根日志器并配置
        self.root_logger = logging.getLogger()
        self.root_logger.setLevel(self.log_level)

        # 清空已有处理器（避免重复输出）
        self.root_logger.handlers.clear()

        # 配置日志处理器
        self._setup_handlers()

        # 标记初始化完成
        self._initialized = True

    def _ensure_log_directory_exists(self) -> None:
        """确保日志目录存在，处理创建失败的异常"""
        try:
            self.log_file_path.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            raise PermissionError(f"无权限创建日志目录：{self.log_file_path}")
        except Exception as e:
            raise RuntimeError(f"创建日志目录失败：{self.log_file_path}，错误：{str(e)}")

    def _build_log_filepath(self) -> Path:
        """构建完整的日志文件路径，确保路径有效"""
        filepath = (self.log_file_path / self.log_filename).resolve()
        # 确保路径是文件（而非目录）
        if filepath.is_dir():
            raise ValueError(f"日志路径指向目录，而非文件：{filepath}")
        return filepath

    class ColoredFormatter(logging.Formatter):
        """
        带颜色的日志格式器（兼容非终端环境）
        - 终端环境显示颜色，非终端（如文件/重定向）自动去掉颜色
        - 兼容Windows（依赖colorama，未安装则自动禁用颜色）
        """
        # ANSI颜色码（兼容大部分终端）
        COLOR_MAP: Dict[str, str] = {
            'DEBUG': '\033[94m',  # 蓝色
            'INFO': '\033[92m',  # 绿色
            'WARNING': '\033[93m',  # 黄色
            'ERROR': '\033[91m',  # 红色
            'CRITICAL': '\033[95m',  # 紫色
        }
        RESET_CODE: str = '\033[0m'

        def __init__(self, fmt: str):
            super().__init__(fmt)

        def format(self, record: logging.LogRecord) -> str:
            """格式化日志，仅在终端环境添加颜色"""
            # 判断是否为终端环境（避免给文件日志加颜色）
            is_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
            if not is_tty or colorama is None:
                return super().format(record)

            # 添加颜色前缀/后缀
            color = self.COLOR_MAP.get(record.levelname, self.RESET_CODE)
            formatted_msg = super().format(record)
            return f"{color}{formatted_msg}{self.RESET_CODE}"

    def _setup_file_handler(self) -> None:
        """配置带轮转的文件日志处理器"""
        # 使用轮转处理器替代普通FileHandler，避免日志文件过大
        file_handler = RotatingFileHandler(
            filename=str(self.log_filepath),
            mode='a',
            maxBytes=self.max_file_size,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        # 文件日志不显示颜色，使用基础格式
        file_handler.setFormatter(logging.Formatter(self.DEFAULT_LOG_FORMAT))
        file_handler.setLevel(self.log_level)
        self.root_logger.addHandler(file_handler)

    def _setup_console_handler(self) -> None:
        """配置控制台日志处理器（支持彩色、健壮的编码处理）"""
        console_handler = logging.StreamHandler(sys.stdout)

        # 彩色格式器
        console_handler.setFormatter(self.ColoredFormatter(self.DEFAULT_LOG_FORMAT))
        console_handler.setLevel(self.log_level)

        # 兼容Python 3.7+的编码配置
        try:
            # 优先使用reconfigure（Python 3.7+）
            console_handler.stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, OSError):
            # 降级处理（兼容低版本Python）
            import io
            console_handler.stream = io.TextIOWrapper(
                console_handler.stream.buffer,
                encoding='utf-8',
                errors='replace',
                line_buffering=True
            )

        self.root_logger.addHandler(console_handler)

    def _setup_handlers(self) -> None:
        """统一配置所有日志处理器"""
        self._setup_file_handler()
        self._setup_console_handler()

    def get_logger(self, name: Optional[str] = None) -> logging.Logger:
        """
        获取指定名称的日志器（核心方法，合并原重复定义）
        - 自动获取调用者名称（类名/模块名）
        - 健壮的栈帧处理，避免异常

        :param name: 日志器名称，None则自动推导
        :return: 配置好的Logger实例
        """
        # 如果指定了名称，直接使用
        if name is not None:
            return logging.getLogger(name)

        # 自动推导调用者名称（健壮的栈帧处理）
        try:
            # 向上查找栈帧：get_logger -> 调用者 -> 目标帧
            frame = inspect.currentframe()
            if frame is None:
                return logging.getLogger("unknown")

            # 逐层向上找，避免本类内部调用的干扰
            caller_frame = frame
            for _ in range(2):
                caller_frame = caller_frame.f_back
                if caller_frame is None:
                    break

            if caller_frame is None:
                return logging.getLogger("unknown")

            # 尝试获取类名/模块名
            locals_dict = caller_frame.f_locals
            if 'self' in locals_dict:
                name = locals_dict['self'].__class__.__name__
            elif 'cls' in locals_dict:
                name = locals_dict['cls'].__name__
            else:
                name = caller_frame.f_globals.get('__name__', 'root')
        except Exception:
            # 任何异常都降级为默认名称，避免日志系统崩溃
            name = "default"
        finally:
            # 强制释放栈帧，避免内存泄漏
            del frame
            del caller_frame

        return logging.getLogger(name)

    def set_log_level(self, level: int) -> None:
        """
        动态修改全局日志级别（新增功能）
        :param level: 日志级别，如 logging.DEBUG / logging.INFO
        """
        self.log_level = level
        self.root_logger.setLevel(level)
        # 同步修改所有处理器的级别
        for handler in self.root_logger.handlers:
            handler.setLevel(level)

    def close_handlers(self) -> None:
        """
        关闭所有日志处理器（新增功能，避免资源泄漏）
        适用于程序优雅退出时调用
        """
        for handler in self.root_logger.handlers:
            handler.close()
            self.root_logger.removeHandler(handler)

    @classmethod
    def reset_singleton(cls) -> None:
        """重置单例（用于单元测试，新增功能）"""
        with cls._lock:
            cls._instance = None
            cls._initialized = False

    def __call__(self, name: Optional[str] = None) -> logging.Logger:
        """支持实例作为函数调用，保持原有用法"""
        return self.get_logger(name)


# ------------------------------
# 使用示例
# ------------------------------
if __name__ == "__main__":
    # 初始化日志配置（单例，仅首次生效）
    log_config = LoggingConfig(
        log_file_path=Path("./logs"),
        log_filename="demo.log",
        log_level=logging.DEBUG
    )

    # 获取日志器（自动推导名称）
    logger = log_config.get_logger()
    logger.debug("这是DEBUG级别的日志（蓝色）")
    logger.info("这是INFO级别的日志（绿色）")
    logger.warning("这是WARNING级别的日志（黄色）")
    logger.error("这是ERROR级别的日志（红色）")
    logger.critical("这是CRITICAL级别的日志（紫色）")

    # 手动指定名称
    custom_logger = log_config.get_logger("CustomModule")
    custom_logger.info("自定义名称的日志器")

    # 动态修改日志级别
    log_config.set_log_level(logging.WARNING)
    logger.info("这行INFO日志不会输出（级别已调整为WARNING）")
    logger.warning("这行WARNING日志正常输出")

    # 优雅关闭（程序退出时调用）
    log_config.close_handlers()
