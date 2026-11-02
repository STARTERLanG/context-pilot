"""应用配置：读写 ~/.context-pilot/config.toml。

配置与密钥都在用户目录，不进版本库。密钥只从配置读取，不写日志。
写回时整体重渲染模板，保证文件结构与字段注释始终一致。
"""

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
class Config:
    general: GeneralConfig = field(default_factory=GeneralConfig)
    llm: LlmConfig = field(default_factory=LlmConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    behavior: BehaviorConfig = field(default_factory=BehaviorConfig)
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
    raw_shortcuts = data.get("shortcuts", {})

    return Config(
        general=GeneralConfig(
            project_root=general.get("project_root", ""),
            hotkey=general.get("hotkey", "ctrl+shift+e"),
            toggle_hotkey=general.get("toggle_hotkey", "ctrl+alt+p"),
            agent=general.get("agent", "claude"),
        ),
        llm=LlmConfig(timeout=float(llm.get("timeout", 60.0))),
        memory=MemoryConfig(enabled=bool(memory.get("enabled", True))),
        context=ContextConfig(
            max_tokens=int(context.get("max_tokens", 6000)),
            rules_tokens=int(context.get("rules_tokens", 1500)),
            memory_tokens=int(context.get("memory_tokens", 1000)),
            code_tokens=int(context.get("code_tokens", 3500)),
        ),
        behavior=BehaviorConfig(
            autostart=bool(behavior.get("autostart", False)),
            auto_copy=bool(behavior.get("auto_copy", True)),
            close_to_tray=bool(behavior.get("close_to_tray", True)),
        ),
        shortcuts=ShortcutsConfig(
            scheme=str(raw_shortcuts.get("scheme", DEFAULT_SCHEME)),
            **{
                action: str(raw_shortcuts.get(action, ""))
                for action in ACTION_IDS
            },
        ),
    )


def save(config: Config, base_dir: Path | None = None) -> None:
    """整体重渲染配置文件。"""
    path = config_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render(config), encoding="utf-8")


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
