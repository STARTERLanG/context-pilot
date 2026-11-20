"""应用配置：读写 ~/.context-pilot/config.toml。

配置与密钥都在用户目录，不进版本库。密钥只从配置读取，不写日志。
写回时整体重渲染模板，保证文件结构与字段注释始终一致。
"""

import os
import tempfile
import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path

from context_pilot.core.models import ContextBudget
from context_pilot.core.shortcuts import (
    ACTION_IDS,
    DEFAULT_SCHEME,
    SCHEME_BY_ID,
    canonical,
    normalize_bindings,
    scheme_bindings,
)

_DEFAULT_DIR = Path.home() / ".context-pilot"
_CONFIG_NAME = "config.toml"

_TRUE_VALUES = frozenset({"true", "1", "yes", "on"})
_FALSE_VALUES = frozenset({"false", "0", "no", "off"})


def _as_bool(value, default: bool) -> bool:
    """显式解析布尔：bool("false") 是 True，直接用会把配置语义反转。"""
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in _TRUE_VALUES:
            return True
        if text in _FALSE_VALUES:
            return False
    return default


def _as_float(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_str(value, default: str = "") -> str:
    return value if isinstance(value, str) else default


@dataclass(frozen=True)
class GeneralConfig:
    project_root: str = ""
    hotkey: str = "ctrl+shift+e"
    toggle_hotkey: str = "ctrl+alt+p"  # 显示/关闭界面（切换态）
    agent: str = "claude"


@dataclass(frozen=True)
class LlmConfig:
    """LLM 调用超时。

    端点 / 密钥 / 模型名 / 是否走真实模型，全部由「模型配置」库
    （profiles.db 里已生效的条目）决定。这里不再保留 base_url / api_key /
    model / provider：同一个问题有两处真实来源时，改了配置文件却按数据库
    调用，用户无从判断哪边说了算。
    """

    timeout: float = 60.0


@dataclass(frozen=True)
class MemoryConfig:
    enabled: bool = True


@dataclass(frozen=True)
class ContextConfig:
    max_tokens: int = 6000
    rules_tokens: int = 1500
    memory_tokens: int = 1000
    code_tokens: int = 3500

    def as_budget(self) -> "ContextBudget":
        """转成 core 层的预算结构，供 Pipeline 注入。

        存在两个表态是有意的：本处在配置层（字段名带 _tokens、面向 TOML 与 UI），
        core.ContextBudget 是管线层（字段名短、不含持久化语义）。装配层负责桥接，
        避免 core 反向依赖 config。
        """
        return ContextBudget(
            max_tokens=self.max_tokens,
            rules=self.rules_tokens,
            memory=self.memory_tokens,
            code=self.code_tokens,
        )


@dataclass(frozen=True)
class ShortcutsConfig:
    """窗口内快捷键：方案 + 每个动作的实际绑定。

    绑定以「方案ID → 动作ID」的扁平字段存储，而不是「方案 + 差量覆盖」：
    差量会让「这条到底谁说了算」变得难解释（改了方案又改了某个键，再改回
    方案该保留哪个？）。整体存储则没有歧义——切方案就是整体替换，改单个键
    就是改这一条，所见即所存。

    依然保留 scheme 字段：仅用于记住「上次套用的是哪套」，方便用户一键重置。
    """

    scheme: str = DEFAULT_SCHEME
    enhance: str = ""
    rerun: str = ""
    use: str = ""
    close: str = ""
    view_enhanced: str = ""
    view_diff: str = ""
    view_context: str = ""

    def __post_init__(self) -> None:
        """归一化写法并按下方案默认值补齐，让实例一律可直接用。

        写回总是规范形式（escape→esc、return→enter）：捕获按键时 Qt 与 platform
        层给出的写法并不统一，若原样落盘，配置里会长出同一物理键的两种写法，
        既难读，也让「是否重复绑定」的判断出现分歧。
        """
        scheme = self.scheme or DEFAULT_SCHEME
        if scheme not in SCHEME_BY_ID:
            scheme = DEFAULT_SCHEME
        object.__setattr__(self, "scheme", scheme)
        defaults = scheme_bindings(scheme)
        for action in ACTION_IDS:
            value = canonical(getattr(self, action)) or defaults[action]
            object.__setattr__(self, action, value)

    def raw(self) -> dict[str, str]:
        """原样返回存下来的值（空串补方案默认），**不做修复**。

        校验要盯的就是用户存的原文：若校验看的是修复后的值，那「非法值」根本
        没机会被报出来（一切都已经被悄悄改好了），用户改了个键却不知道为什么
        没生效。修复过的表留给真正要去注册快捷键的那一侧。
        """
        defaults = scheme_bindings(self.scheme)
        return {
            action: (canonical(getattr(self, action)) or defaults[action])
            for action in ACTION_IDS
        }

    def bindings(self) -> dict[str, str]:
        """取**必定可用**的绑定表：非法值回退方案默认，重复的去重。

        这条是「窗口永远打得开、快捷键永远按得动」的兜底——设置页负责把问题
        报给用户，但不该让一个坏值把主窗口变成没有快捷键的窗口。
        """
        return normalize_bindings(self.raw(), self.scheme)

    def with_binding(self, action: str, sequence: str) -> "ShortcutsConfig":
        """返回改了单个动作绑定的新实例（不可变）。"""
        if action not in ACTION_IDS:
            raise ValueError(f"未知的快捷键动作：{action}")
        return replace(self, **{action: sequence})

    def with_scheme(self, scheme: str) -> "ShortcutsConfig":
        """返回整套换成指定方案的新实例。"""
        bindings = scheme_bindings(scheme)
        return ShortcutsConfig(scheme=scheme, **bindings)


@dataclass(frozen=True)
class BehaviorConfig:
    autostart: bool = False
    auto_copy: bool = True  # 点「使用」后自动写回剪贴板
    close_to_tray: bool = True  # 关窗只隐藏，不退出


@dataclass(frozen=True)
class EnhanceHotkeyConfig:
    """全局增强热键（ctrl+shift+e）的专用默认值。

    与主窗口顶行的「项目 / 模型 / 风格」选择**相互独立**：全局热键在后台触发时，
    主窗口的会话级选择可能早已被切走，故热键需要一份属于自己的默认模式与默认模型。

    - ``default_style``：默认优化模式 key（复用 OUTPUT_STYLES 的四档内置模式），
      留空或非法时回落「结构化增强」（default）。
    - ``default_model_id``：默认模型配置 id（指向 profiles.db 的 model_profiles）。
      留空表示「未指定」，触发时按回落规则取用：优先当前选中的目标，否则唯一
      已生效的配置，再否则报错提示。
    - ``auto_paste``：是否自动「全选→复制→增强→粘贴回写」。为 True 时热键触发
      会先全选当前输入框文本、复制、增强后自动粘贴回写；为 False 时只读取已
      选中文本、增强后把结果写回剪贴板，由用户自行粘贴。
    - ``default_project_id``：默认项目 id（指向 projects.db 的项目条目）。
      留空或为 ``default`` 表示「无项目」（不检索项目代码、仅优化文本）；指定了
      某个已索引的项目时，热键增强会检索该项目代码作为上下文。
    """

    default_style: str = "default"
    default_model_id: str = ""
    auto_paste: bool = False
    default_project_id: str = ""


@dataclass(frozen=True)
class Config:
    general: GeneralConfig = field(default_factory=GeneralConfig)
    llm: LlmConfig = field(default_factory=LlmConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    behavior: BehaviorConfig = field(default_factory=BehaviorConfig)
    enhance_hotkey: EnhanceHotkeyConfig = field(default_factory=EnhanceHotkeyConfig)
    shortcuts: ShortcutsConfig = field(default_factory=ShortcutsConfig)


def config_path(base_dir: Path | None = None) -> Path:
    return (base_dir or _DEFAULT_DIR) / _CONFIG_NAME


def load(base_dir: Path | None = None) -> Config:
    """读取配置；文件不存在时写入默认模板并返回默认值。"""
    path = config_path(base_dir)
    if not path.exists():
        save(Config(), base_dir)
        return Config()

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    general = data.get("general", {})
    llm = data.get("llm", {})
    memory = data.get("memory", {})
    context = data.get("context", {})
    behavior = data.get("behavior", {})
    enhance_hotkey = data.get("enhance_hotkey", {})
    raw_shortcuts = data.get("shortcuts", {})

    # 逐字段回落默认值：手改坏一个字段不该让整个配置读不出来，
    # 更不该让 bool("false") 把「关闭」静默变成「开启」。
    defaults = Config()
    return Config(
        general=GeneralConfig(
            project_root=_as_str(general.get("project_root"), defaults.general.project_root),
            hotkey=_as_str(general.get("hotkey"), defaults.general.hotkey),
            toggle_hotkey=_as_str(
                general.get("toggle_hotkey"), defaults.general.toggle_hotkey
            ),
            agent=_as_str(general.get("agent"), defaults.general.agent),
        ),
        llm=LlmConfig(
            timeout=_as_float(llm.get("timeout"), defaults.llm.timeout),
        ),
        memory=MemoryConfig(
            enabled=_as_bool(memory.get("enabled"), defaults.memory.enabled),
        ),
        context=ContextConfig(
            max_tokens=_as_int(context.get("max_tokens"), defaults.context.max_tokens),
            rules_tokens=_as_int(
                context.get("rules_tokens"), defaults.context.rules_tokens
            ),
            memory_tokens=_as_int(
                context.get("memory_tokens"), defaults.context.memory_tokens
            ),
            code_tokens=_as_int(context.get("code_tokens"), defaults.context.code_tokens),
        ),
        behavior=BehaviorConfig(
            autostart=_as_bool(behavior.get("autostart"), defaults.behavior.autostart),
            auto_copy=_as_bool(behavior.get("auto_copy"), defaults.behavior.auto_copy),
            close_to_tray=_as_bool(
                behavior.get("close_to_tray"), defaults.behavior.close_to_tray
            ),
        ),
        enhance_hotkey=EnhanceHotkeyConfig(
            default_style=_as_str(
                enhance_hotkey.get("default_style"),
                defaults.enhance_hotkey.default_style,
            ),
            default_model_id=_as_str(
                enhance_hotkey.get("default_model_id"),
                defaults.enhance_hotkey.default_model_id,
            ),
            auto_paste=_as_bool(
                enhance_hotkey.get("auto_paste"), defaults.enhance_hotkey.auto_paste
            ),
            default_project_id=_as_str(
                enhance_hotkey.get("default_project_id"),
                defaults.enhance_hotkey.default_project_id,
            ),
        ),
        shortcuts=ShortcutsConfig(
            scheme=_as_str(raw_shortcuts.get("scheme"), DEFAULT_SCHEME),
            **{
                action: _as_str(raw_shortcuts.get(action))
                for action in ACTION_IDS
            },
        ),
    )


def save(config: Config, base_dir: Path | None = None) -> None:
    """整体重渲染配置文件（同目录临时文件 + 原子替换）。

    直接 write_text 遇到写盘中断会留下半截 TOML，下次启动整个配置读不出来。
    同目录的临时文件保证 os.replace 是原子操作，也不会跨文件系统失败。
    """
    path = config_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = _render(config)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{_CONFIG_NAME}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def _toml_str(value: str) -> str:
    """TOML 字符串转义，防止路径中的反斜杠与引号破坏结构。"""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _render(config: Config) -> str:
    lines = [
        "# ContextPilot 配置（由设置界面生成）",
        "",
        "[general]",
        "# 被增强的项目根目录；留空则用启动时的工作目录",
        f"project_root = {_toml_str(config.general.project_root)}",
        "# 全局热键，形如 ctrl+shift+e",
        f"hotkey = {_toml_str(config.general.hotkey)}",
        "# 显示/关闭界面的切换热键，形如 ctrl+alt+p",
        f"toggle_hotkey = {_toml_str(config.general.toggle_hotkey)}",
        "# 目标 Agent：claude / codex / gemini",
        f"agent = {_toml_str(config.general.agent)}",
        "",
        "[llm]",
        "# 端点 / 密钥 / 模型名在设置页「模型配置」中维护（~/.context-pilot/profiles.db）；",
        "# 勾选「已生效」的配置出现在主页面「模型」下拉中。此处只保留调用超时。",
        f"timeout = {config.llm.timeout}",
        "",
        "[memory]",
        f"enabled = {str(config.memory.enabled).lower()}",
        "",
        "[context]",
        f"max_tokens = {config.context.max_tokens}",
        f"rules_tokens = {config.context.rules_tokens}",
        f"memory_tokens = {config.context.memory_tokens}",
        f"code_tokens = {config.context.code_tokens}",
        "",
        "[behavior]",
        f"autostart = {str(config.behavior.autostart).lower()}",
        f"auto_copy = {str(config.behavior.auto_copy).lower()}",
        f"close_to_tray = {str(config.behavior.close_to_tray).lower()}",
        "",
        "[enhance_hotkey]",
        "# 全局增强热键的专用默认值（与主窗口顶行的当前选择相互独立）",
        "# 默认优化模式 key：default/basic/professional/planning（见「优化模式」页）",
        f"default_style = {_toml_str(config.enhance_hotkey.default_style)}",
        "# 默认模型配置 id（profiles.db）；留空表示未指定，触发时按回落规则取用",
        f"default_model_id = {_toml_str(config.enhance_hotkey.default_model_id)}",
        "# 是否自动「全选→复制→增强→粘贴回写」；关闭时仅把结果写回剪贴板",
        f"auto_paste = {str(config.enhance_hotkey.auto_paste).lower()}",
        "# 默认项目 id（projects.db）；留空或 default 表示无项目（不检索代码）",
        f"default_project_id = {_toml_str(config.enhance_hotkey.default_project_id)}",
        "",
        "[shortcuts]",
        "# 窗口内快捷键：scheme 只是「上次套用的方案」，便于一键重置；",
        "# 真正的生效值是下面每一条。改单个键只动那一行即可。",
        "# 除 close 可用 Esc 单键外，其余必须是组合键（Ctrl/Alt/Cmd + 键）。",
        f"scheme = {_toml_str(config.shortcuts.scheme)}",
    ]
    bindings = config.shortcuts.bindings()
    for action in ACTION_IDS:
        lines.append(f"{action} = {_toml_str(bindings[action])}")
    lines.append("")
    return "\n".join(lines)


def with_updates(config: Config, **overrides) -> Config:
    """返回替换了顶层 section 的新配置（不可变对象，便于测试与局部更新）。"""
    return replace(config, **overrides)
