"""兼容转发：热键解析已迁至 context_pilot.shortcuts.keys。

保留此模块只为让历史 import 路径（``from context_pilot.platform.keys import ...``）
继续可用；新代码请直接使用 context_pilot.shortcuts.keys。
"""

from context_pilot.shortcuts.keys import (
    MOD_ALT,
    MOD_CONTROL,
    MOD_NOREPEAT,
    MOD_SHIFT,
    MOD_WIN,
    HotkeyParseError,
    format,
    is_valid,
    parse,
)

__all__ = [
    "MOD_ALT",
    "MOD_CONTROL",
    "MOD_NOREPEAT",
    "MOD_SHIFT",
    "MOD_WIN",
    "HotkeyParseError",
    "format",
    "is_valid",
    "parse",
]
