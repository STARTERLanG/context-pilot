"""热键字符串与 Win32 修饰符/虚拟键码的互转。

纯逻辑模块，不依赖 Qt，便于单测。Qt 的键码在调用侧转成 Win32 虚拟键码后传入
（Qt 键码 → 字符串的映射见本包的 qt_keys.py，刻意与这里分离，保持 keys.py 无 Qt 依赖）。

这是快捷键模块的解析/校验/格式化层：全局热键与窗口内快捷键共用同一套转换，
避免两处各自维护一份键码表。
"""

from context_pilot.shortcuts.errors import HotkeyParseError

__all__ = [
    "HotkeyParseError",
    "MOD_ALT",
    "MOD_CONTROL",
    "MOD_SHIFT",
    "MOD_WIN",
    "MOD_NOREPEAT",
    "parse",
    "format",
    "is_valid",
]

# Win32 修饰符
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

_MOD_NAMES: dict[str, int] = {
    "alt": MOD_ALT,
    "ctrl": MOD_CONTROL,
    "control": MOD_CONTROL,
    "shift": MOD_SHIFT,
    "win": MOD_WIN,
    "super": MOD_WIN,
    # macOS 的 Command（⌘）在 Win32 上等价于 Win 键；cmd/meta/command 均为别名。
    # 跨平台后端各自把该掩码位解释为自己的修饰键（macOS 后端映射为 cmdKey）。
    "cmd": MOD_WIN,
    "meta": MOD_WIN,
    "command": MOD_WIN,
}

# 主键名 → Win32 虚拟键码（覆盖常见键）
_NAMED_KEYS: dict[str, int] = {
    "tab": 0x09, "enter": 0x0D, "return": 0x0D, "esc": 0x1B, "escape": 0x1B,
    "space": 0x20, "backspace": 0x08, "delete": 0x2E, "insert": 0x2D,
    "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    "`": 0xC0, "-": 0xBD, "=": 0xBB, "[": 0xDB, "]": 0xDD,
    "\\": 0xDC, ";": 0xBA, "'": 0xDE, ",": 0xBC, ".": 0xBE, "/": 0xBF,
}

# 键码 → 规范化名称（用于显示与写回配置）
_VK_NAMES: dict[int, str] = {vk: name for name, vk in _NAMED_KEYS.items()}


def _key_to_vk(key: str) -> int:
    if key in _NAMED_KEYS:
        return _NAMED_KEYS[key]
    if len(key) == 1:
        char = key.upper()
        if "A" <= char <= "Z":
            return ord(char)
        if "0" <= char <= "9":
            return ord(char)
    if key.startswith("f") and key[1:].isdigit():
        number = int(key[1:])
        if 1 <= number <= 24:
            return 0x70 + (number - 1)  # F1 = 0x70
    raise HotkeyParseError(f"无法识别的按键：{key}")


def parse(sequence: str) -> tuple[int, int]:
    """把 'ctrl+shift+e' 解析为 (修饰符掩码, 虚拟键码)。"""
    parts = [p.strip().lower() for p in sequence.split("+") if p.strip()]
    if len(parts) < 2:
        raise HotkeyParseError("热键必须包含至少一个修饰键和一个主键")

    modifiers = 0
    for part in parts[:-1]:
        if part not in _MOD_NAMES:
            raise HotkeyParseError(f"无法识别的修饰键：{part}")
        modifiers |= _MOD_NAMES[part]

    if modifiers == 0:
        raise HotkeyParseError("热键必须包含至少一个修饰键")

    main = parts[-1]
    if main in _MOD_NAMES:
        raise HotkeyParseError("主键不能是修饰键")
    return modifiers, _key_to_vk(main)


def format(modifiers: int, vk: int) -> str:
    """把修饰符掩码与虚拟键码转回规范字符串。"""
    parts: list[str] = []
    if modifiers & MOD_CONTROL:
        parts.append("ctrl")
    if modifiers & MOD_ALT:
        parts.append("alt")
    if modifiers & MOD_SHIFT:
        parts.append("shift")
    if modifiers & MOD_WIN:
        parts.append("win")

    if vk in _VK_NAMES:
        parts.append(_VK_NAMES[vk])
    elif 0x41 <= vk <= 0x5A:
        parts.append(chr(vk).lower())
    elif 0x30 <= vk <= 0x39:
        parts.append(chr(vk))
    elif 0x70 <= vk <= 0x87:
        parts.append(f"f{vk - 0x70 + 1}")
    else:
        raise HotkeyParseError(f"无法格式化的虚拟键码：0x{vk:X}")
    return "+".join(parts)


def is_valid(sequence: str) -> bool:
    """校验字符串是否可作为热键。"""
    try:
        parse(sequence)
    except HotkeyParseError:
        return False
    return True
