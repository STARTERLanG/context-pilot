"""窗口内快捷键：动作清单、预设方案与合法性校验。

纯逻辑模块，不依赖 Qt——规则必须能被单测独立锁住，QML 只负责呈现与上报按键。

放在 core 层而不是 ui 层，是因为 config.py 落盘时需要用同一套规则做校验，
而 config 不能反向依赖 ui。

核心约束（本模块的立身之本）：
    **除 Esc / F1-F12 这类非打印键外，所有绑定必须是组合键。**
    单字母键一旦成为快捷键，用户在输入框里打字就会被当成命令——视图乱跳、
    内容还照常输进去，是这类功能最典型的翻车方式。与其靠「判断焦点」去打
    补丁，不如从规则上禁止。
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from context_pilot.platform.keys import HotkeyParseError, format as format_hotkey, parse

# Qt 的键序列里 Ctrl 在 macOS 上自动映射为 Command（⌘），无需另设 Mac 分支

# 允许「无修饰键」单独成键的白名单：都是不产生字符的键，不存在打字冲突。
# 字母、数字、标点一律不在其中。
NAKED_KEYS: frozenset[str] = frozenset({"esc", "escape"} | {f"f{i}" for i in range(1, 13)})

# Enter 与 Return 是同一个物理键的两种写法（小键盘 vs 主键盘），互为别名；
# Esc 同理有两种写法。冲突检测要先归一化，否则 ctrl+enter 与 ctrl+return 会被
# 当成两个不同的绑定，重复检测就失效了。
_ENTER_ALIAS = {"enter": "return", "return": "enter"}
_CANONICAL_ALIAS = {"return": "enter", "escape": "esc"}

# 被文本编辑控件占用的组合：抢走它们会让输入框里的复制/粘贴/撤销/选词失效。
# 这是「功能性倒退」而非「不好用」，所以是阻断级错误，不是提示。
# 注意这里只列 Qt 的 TextInput/TextEdit 真正会吞掉的那些；ctrl+shift+c 之类
# Qt 并未绑定，留给别的功能使用。
RESERVED_COMBOS: frozenset[str] = frozenset(
    {
        "ctrl+a",  # 全选
        "ctrl+c",  # 复制
        "ctrl+v",  # 粘贴
        "ctrl+x",  # 剪切
        "ctrl+z",  # 撤销
        "ctrl+y",  # 重做
        "ctrl+insert",  # 复制
        "shift+insert",  # 粘贴
        "ctrl+backspace",  # 删词
        "ctrl+delete",  # 删词
        "ctrl+left",  # 光标按词左移
        "ctrl+right",  # 光标按词右移
        "ctrl+up",
        "ctrl+down",
        "ctrl+home",
        "ctrl+end",
    }
)


@dataclass(frozen=True)
class ShortcutAction:
    """一个可绑定的窗口内动作。"""

    id: str
    label: str
    desc: str
    # 是否允许绑定成无修饰键的单键（目前只有 close 用得上 Esc）
    allow_naked: bool = False


@dataclass(frozen=True)
class ShortcutScheme:
    """一套完整的绑定方案。切换方案即整体替换所有绑定，不做部分覆盖。"""

    id: str
    label: str
    desc: str
    bindings: tuple[tuple[str, str], ...]  # 有序，保证渲染与测试的确定性


@dataclass(frozen=True)
class ShortcutIssue:
    """绑定表里的一个问题。level 为 error 时不允许保存。"""

    action: str  # 涉及的动作 id；空串表示不涉及单个动作
    level: str  # "error" | "warning"
    message: str


ACTIONS: tuple[ShortcutAction, ...] = (
    ShortcutAction("enhance", "增强", "按当前输入跑一次增强"),
    ShortcutAction("rerun", "重新增强", "用同样的输入重跑一次"),
    ShortcutAction("use", "使用增强结果", "写入剪贴板并关闭窗口"),
    ShortcutAction("close", "关闭窗口", "隐藏到托盘，Esc 是惯例", allow_naked=True),
    ShortcutAction("view_enhanced", "视图 · 增强结果", "切到增强结果视图"),
    ShortcutAction("view_diff", "视图 · 差异", "切到原文与结果的差异视图"),
    ShortcutAction("view_context", "视图 · 上下文", "切到上下文来源视图"),
)

ACTION_IDS: tuple[str, ...] = tuple(a.id for a in ACTIONS)
ACTION_BY_ID: dict[str, ShortcutAction] = {a.id: a for a in ACTIONS}


def _scheme(id: str, label: str, desc: str, bindings: dict[str, str]) -> ShortcutScheme:
    """按 ACTIONS 的固定顺序归一化绑定，避免字典顺序影响落盘结果。"""
    return ShortcutScheme(
        id=id,
        label=label,
        desc=desc,
        bindings=tuple((action, bindings[action]) for action in ACTION_IDS),
    )


SCHEMES: tuple[ShortcutScheme, ...] = (
    _scheme(
        "balanced",
        "推荐",
        "动作用 Ctrl，视图用 Alt，两者与文本编辑组合键完全不重叠",
        {
            "enhance": "ctrl+enter",
            "rerun": "ctrl+r",
            "use": "ctrl+u",
            "close": "esc",
            "view_enhanced": "alt+e",
            "view_diff": "alt+d",
            "view_context": "alt+c",
        },
    ),
    _scheme(
        "ctrl",
        "纯 Ctrl 系",
        "全部落在 Ctrl 上，适合习惯浏览器/编辑器手感的人",
        {
            "enhance": "ctrl+enter",
            "rerun": "ctrl+r",
            "use": "ctrl+u",
            "close": "ctrl+w",
            "view_enhanced": "ctrl+e",
            "view_diff": "ctrl+d",
            "view_context": "ctrl+shift+c",
        },
    ),
    _scheme(
        "alt",
        "纯 Alt 系",
        "Ctrl 组合被系统或其它软件占用时的兜底方案",
        {
            "enhance": "alt+enter",
            "rerun": "alt+r",
            "use": "alt+u",
            "close": "esc",
            "view_enhanced": "alt+e",
            "view_diff": "alt+d",
            "view_context": "alt+c",
        },
    ),
)

SCHEME_BY_ID: dict[str, ShortcutScheme] = {s.id: s for s in SCHEMES}
SCHEME_OPTIONS: tuple[tuple[str, str], ...] = tuple((s.id, s.label) for s in SCHEMES)
DEFAULT_SCHEME = "balanced"


def scheme_bindings(scheme_id: str) -> dict[str, str]:
    """取某方案的全部绑定；未知方案回退默认方案（手改坏配置不该让窗口打不开）。"""
    return dict(SCHEME_BY_ID.get(scheme_id, SCHEME_BY_ID[DEFAULT_SCHEME]).bindings)


def normalize_sequence(sequence: str) -> str:
    """规范化写法：去空白、转小写、压缩 '+' 周围空格。"""
    parts = [p.strip().lower() for p in sequence.split("+") if p.strip()]
    return "+".join(parts)


def canonical(sequence: str) -> str:
    """归一化到同一物理键的唯一写法：enter/return 合一，escape/esc 合一。"""
    parts = normalize_sequence(sequence).split("+")
    if parts:
        parts[-1] = _CANONICAL_ALIAS.get(parts[-1], parts[-1])
    return "+".join(parts)


def variants(sequence: str) -> tuple[str, ...]:
    """返回应同时注册的所有写法（Enter 连带小键盘 Return），供 Qt 一次注册。"""
    seq = normalize_sequence(sequence)
    if not seq:
        return ()
    parts = seq.split("+")
    last = parts[-1]
    alias = _ENTER_ALIAS.get(last)
    if alias is None:
        return (seq,)
    parts[-1] = alias
    return (seq, "+".join(parts))


def sequence_error(sequence: str, *, allow_naked: bool = False) -> str:
    """校验单个绑定串；合法返回空串，否则返回可直接展示给用户的原因。"""
    seq = normalize_sequence(sequence)
    if not seq:
        return "未绑定"

    main = seq.split("+")[-1]
    # 无修饰键：只有白名单里的非打印键可以通过
    if len(seq.split("+")) == 1:
        if not allow_naked:
            return f"「{seq}」不是组合键，必须带 Ctrl / Alt / Cmd 等修饰键"
        if main not in NAKED_KEYS:
            return f"「{seq}」不能单独作为快捷键（只有 Esc / F1-F12 可以）"
        return ""

    try:
        parse(seq)
    except HotkeyParseError as exc:
        return f"无法识别：{exc}"

    if canonical(seq) in RESERVED_COMBOS:
        return "该组合已被文本编辑占用（复制 / 粘贴 / 撤销等），换一个吧"
    return ""


def conflicts_with_typing(sequence: str) -> bool:
    """这个键序列会不会和打字抢输入。

    只看「无修饰键且非 Esc / F1-F12」这一件事：组合键一律不冲突（Ctrl+E 在输入框
    里不会被打出来），Esc 与功能键不产生字符也不冲突。单字母、数字、标点才冲突。
    主窗口与测试都用它做同一道闸，避免两边各写一份判断。
    """
    return bool(sequence_error(sequence, allow_naked=True))


def validate_bindings(
    bindings: Mapping[str, str],
    global_hotkeys: Iterable[str] = (),
) -> list[ShortcutIssue]:
    """校验整张绑定表。返回空列表表示可以直接保存。

    error 级（阻断保存）：未绑定 / 非组合键 / 无法识别 / 占用了编辑组合 / 重复。
    warning 级（可保存）：与全局热键相同——两者命名空间独立，但同按会双触发。
    """
    issues: list[ShortcutIssue] = []

    for action in ACTIONS:
        seq = normalize_sequence(bindings.get(action.id, ""))
        error = sequence_error(seq, allow_naked=action.allow_naked)
        if error:
            issues.append(ShortcutIssue(action.id, "error", f"{action.label}：{error}"))

    # 重复：同一组内不允许两个动作抢同一个键
    seen: dict[str, str] = {}
    for action in ACTIONS:
        key = canonical(bindings.get(action.id, ""))
        if not key:
            continue
        seq = normalize_sequence(bindings[action.id])
        if key in seen:
            issues.append(
                ShortcutIssue(
                    action.id,
                    "error",
                    f"{action.label} 与 {seen[key]} 重复绑定了 {seq}",
                )
            )
        else:
            seen[key] = action.label

    # 与全局热键碰撞：提示即可，不强拦——用户可能有意为之
    globals_ = {canonical(g) for g in global_hotkeys if normalize_sequence(g)}
    for action in ACTIONS:
        seq = normalize_sequence(bindings.get(action.id, ""))
        if canonical(seq) in globals_:
            issues.append(
                ShortcutIssue(
                    action.id,
                    "warning",
                    f"{action.label} 与全局热键相同，窗口聚焦时会双触发",
                )
            )

    return issues


def normalize_bindings(
    raw: Mapping[str, str] | None, scheme_id: str = DEFAULT_SCHEME
) -> dict[str, str]:
    """按方案补全 / 修正一张绑定表，使其必定可用。

    用于从配置读取时兜底：缺失的用方案默认值，非法的同样回退到方案默认值
    （手改坏的 toml、旧版本遗留的写法都不会让窗口打不开）。
    """
    defaults = scheme_bindings(scheme_id)
    source = dict(raw or {})
    result: dict[str, str] = {}
    for action in ACTIONS:
        seq = normalize_sequence(source.get(action.id, ""))
        if sequence_error(seq, allow_naked=action.allow_naked):
            seq = defaults[action.id]
        result[action.id] = seq

    # 去重：后者若撞上前者，回退到方案默认值（默认值之间保证不重复）
    taken: dict[str, str] = {}
    for action in ACTIONS:
        key = canonical(result[action.id])
        if key in taken:
            result[action.id] = defaults[action.id]
            key = canonical(result[action.id])
        taken[key] = action.id
    return result


def format_sequence(modifiers: int, vk: int) -> str:
    """把 Win32 修饰符与虚拟键码转成绑定串（捕获按键时用）。"""
    return format_hotkey(modifiers, vk)


_DISPLAY_NAMES: dict[str, str] = {
    "ctrl": "Ctrl",
    "alt": "Alt",
    "shift": "Shift",
    "win": "Win",
    "enter": "Enter",
    "return": "Return",
    "esc": "Esc",
    "space": "Space",
    "tab": "Tab",
}


def describe(sequence: str) -> str:
    """给用户看的展示文案：ctrl+enter → Ctrl+Enter。macOS 上 Ctrl 即 ⌘。"""
    parts = normalize_sequence(sequence).split("+")
    shown = []
    for part in parts:
        if part in _DISPLAY_NAMES:
            shown.append(_DISPLAY_NAMES[part])
        elif part.startswith("f") and part[1:].isdigit():
            shown.append(f"F{int(part[1:])}")
        else:
            shown.append(part.upper())
    return "+".join(shown)
