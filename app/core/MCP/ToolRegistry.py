"""
工具注册器模块 (v2 — 配置驱动版)

核心设计：
  - 根据 YAML 中各平台 platforms.xxx.tools 配置，按需实例化工具
  - 不同平台可启用/禁用不同工具、使用不同参数
  - 新增工具只需：(1)写工具类 (2)maps.py加Schema (3)ToolMetaRegistry注册 (4)YAML配置
"""

import inspect
from typing import Dict, Callable, Any

from app.core.config_manager import config
from app.core.MCP.maps import ALL_TOOLS
from app.core.MCP.ToolMetaRegistry import (
    get_tool_class,
    get_enable_tool_names,
)


class LazyToolProxy:
    """
    工具懒加载代理

    不立即创建真实工具实例，而是在第一次 __call__ 时才实例化并执行。
    之后缓存实例，后续调用直接复用。

    用法:
        proxy = LazyToolProxy(tool_class, tool_name, build_kwargs_fn)
        result = await proxy(query="xxx")   # ← 此时才真正创建实例
        result2 = await proxy(query="yyy")  # ← 复用已缓存的实例
    """

    def __init__(self, tool_cls: type, tool_name: str, build_kwargs_fn: Callable[[], dict]):
        """
        Args:
            tool_cls:         工具类 (如 InternetData)
            tool_name:        工具名 (如 "get_internet_data")
            build_kwargs_fn:  无参函数，返回构造该工具所需的 kwargs 字典
                               （延迟求值，确保调用时拿到最新上下文）
        """
        self._tool_cls = tool_cls
        self._tool_name = tool_name
        self._build_kwargs_fn = build_kwargs_fn
        self._instance: Any = None  # 缓存的实例
        self._real_func: Callable = None  # 缓存的函数引用
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        """是否已经完成真实实例化"""
        return self._initialized

    def _ensure_initialized(self):
        """首次使用时触发真实实例化"""
        if not self._initialized:
            kwargs = self._build_kwargs_fn()
            self._instance = self._tool_cls(**kwargs)
            self._real_func = self._instance.get_function()
            self._initialized = True

    def __call__(self, *args, **kwargs):
        """代理调用 —— 首次调用时自动初始化，之后直接转发"""
        self._ensure_initialized()
        return self._real_func(*args, **kwargs)

    def get_real_instance(self) -> Any:
        """获取真实的工具实例（用于调试或直接操作）"""
        self._ensure_initialized()
        return self._instance


class ToolRegistry:
    """
    配置驱动的工具注册器（懒加载）

    行为完全由 YAML 配置控制：
      create_image:
        enabled: false   → 不注册、不加载、LLM 不知道它的存在
        enabled: true    → 注册 Schema + Proxy，LLM 可调用，首次使用时才实例化

    Usage:
        >>> registry = ToolRegistry(
        ...     platform_name="zhihu",
        ...     platform_config=config.platforms["zhihu"],
        ...     client=client,
        ... )
        >>> registry.get_all_tool_functions().keys()
        dict_keys(['get_internet_data'])   # create_image 被 enabled:false 过滤掉了
    """

    def __init__(self,
                 platform_name: str,
                 platform_config: dict,
                 client: Any = None,
                 model_name: str = None):
        """
        Args:
            platform_name:    平台标识
            platform_config:  平台完整配置段
            client:           LLM 客户端
            model_name:       默认模型名
        """
        self.platform_name = platform_name
        self.platform_config = platform_config or {}
        self.client = client
        self.model_name = model_name or self._extract_model_name(platform_config)


        # 输出结果
        self.tool_definitions: list[dict] = []
        # 注意：这里存的是 LazyToolProxy 对象，不是真实函数！
        # 但对外接口不变，因为 LazyToolProxy 实现了 __call__
        self.tool_functions: Dict[str, Callable] = {}
        # 记录哪些工具已被实际初始化（用于调试/监控）
        self._initialized_tools: set[str] = set()

        self._register_tools()

    # ------------------------------------------------------------------ #
    #  公共接口（与 v2 完全一致）
    # ------------------------------------------------------------------ #

    def get_tools(self) -> list[dict]:
        """获取当前平台启用工具的 schema 定义列表"""
        return self.tool_definitions

    def get_tool_function(self, tool_name: str) -> Callable | None:
        """获取可调用对象（可能是 LazyToolProxy）"""
        return self.tool_functions.get(tool_name)

    def get_all_tool_functions(self) -> Dict[str, Callable]:
        """获取全部 {tool_name: callable} 映射"""
        return self.tool_functions

    def get_initialized_tools(self) -> list[str]:
        """【新增】查看哪些工具已经被真实实例化（调试用）"""
        return sorted(self._initialized_tools)

    # ------------------------------------------------------------------ #
    #  内部逻辑
    # ------------------------------------------------------------------ #

    def _extract_model_name(self, pf_config: dict) -> str | None:
        model_cfg = pf_config.get("model", {}) if pf_config else {}
        return model_cfg.get("name")


    def _register_tools(self):
        """根据 YAML 配置注册工具（enabled:false 的完全不处理）"""

        tools_cfg = self.platform_config.get("tools", {})

        # ---- 第1步：从 YAML 中筛选出 enabled=True 的工具 ----
        target_names = get_enable_tool_names(tools_cfg)

        if not target_names:
            print(f"[ToolRegistry] 平台 '{self.platform_name}' 无可用工具 (或全部 disabled)")
            return

        # ---- 第2步：构建 schema 快查表 ----
        all_schemas_by_name: dict[str, dict] = {
            t["function"]["name"]: t
            for t in ALL_TOOLS
            if "function" in t and "name" in t["function"]
        }

        # ---- 第3步：逐个注册 LazyToolProxy ----
        for tool_name in target_names:

            # a) 收集 schema（发给 LLM 的工具定义）
            if tool_name in all_schemas_by_name:
                self.tool_definitions.append(all_schemas_by_name[tool_name])

            # b) 获取工具类
            tool_cls = get_tool_class(tool_name)
            if tool_cls is None:
                print(f"[ToolRegistry] ⚠️ 工具 '{tool_name}' 未在元数据表中注册，跳过")
                continue

            specific_cfg = tools_cfg.get(tool_name, {})

            # c) 创建 Proxy（极轻量，不触发 __init__）
            proxy = LazyToolProxy(
                tool_cls=tool_cls,
                tool_name=tool_name,
                # 闭包延迟捕获 —— 首次 __call__ 时才执行
                build_kwargs_fn=lambda _cls=tool_cls, _name=tool_name, _cfg=specific_cfg:
                    self._build_kwargs(_cls, _name, _cfg),
            )

            self.tool_functions[tool_name] = proxy

            print(f"[ToolRegistry] 🔮 已注册(懒加载) '{tool_name}' "
                  f"(平台: {self.platform_name})")

    def _build_kwargs(self, tool_cls: type, tool_name: str,
                      tool_config: dict) -> dict:
        """
        组装工具构造参数

        这个方法会在 LazyToolProxy 首次被调用时执行，
        所以此时 client/model_name 已经是最终值。
        """

        merged = {
            # 通用依赖
            "client": self.client,
            "model_name": self.model_name,
            "_platform_config": self.platform_config,
            # 工具特定配置
            **(tool_config if isinstance(tool_config, dict) else {}),
        }

        # 用 inspect 自动匹配签名
        try:
            sig = inspect.signature(tool_cls.__init__)
            accepted = set(sig.parameters.keys()) - {"self"}
        except (ValueError, TypeError):
            accepted = set()

        filtered = {k: v for k, v in merged.items() if k in accepted}

        # 记录实际初始化
        self._initialized_tools.add(tool_name)

        return filtered


# =================================================================== #
#  全局工厂函数
# =================================================================== #

def create_tool_registry(platform_name: str,
                         platform_config: dict,
                         client: Any = None,
                         model_name: str = None) -> ToolRegistry:
    """
    创建工具注册器实例

    Args:
        platform_name:    平台名
        platform_config:  平台完整配置
        client:           LLM 客户端
        model_name:       模型名
    """
    return ToolRegistry(
        platform_name=platform_name,
        platform_config=platform_config,
        client=client,
        model_name=model_name,
    )
