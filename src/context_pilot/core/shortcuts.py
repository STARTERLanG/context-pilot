"""兼容转发：窗口内快捷键规则已迁至 context_pilot.shortcuts.registry。

保留此模块只为让历史 import 路径（``from context_pilot.core.shortcuts import ...``）
继续可用；新代码请直接使用 context_pilot.shortcuts.registry。
"""

from context_pilot.shortcuts.registry import (
    ACTIONS,
    ACTION_BY_ID,
    ACTION_IDS,
    DEFAULT_SCHEME,
    NAKED_KEYS,
    SCHEMES,
    SCHEME_BY_ID,
    SCHEME_OPTIONS,
    ShortcutAction,
    ShortcutIssue,
    ShortcutScheme,
    canonical,
    conflicts_with_typing,
    describe,
    format_sequence,
    normalize_bindings,
    normalize_sequence,
    scheme_bindings,
    sequence_error,
    validate_bindings,
    variants,
)

__all__ = [
    "ACTIONS",
    "ACTION_BY_ID",
    "ACTION_IDS",
    "DEFAULT_SCHEME",
    "NAKED_KEYS",
    "SCHEMES",
    "SCHEME_BY_ID",
    "SCHEME_OPTIONS",
    "ShortcutAction",
    "ShortcutIssue",
    "ShortcutScheme",
    "canonical",
    "conflicts_with_typing",
    "describe",
    "format_sequence",
    "normalize_bindings",
    "normalize_sequence",
    "scheme_bindings",
    "sequence_error",
    "validate_bindings",
    "variants",
]
