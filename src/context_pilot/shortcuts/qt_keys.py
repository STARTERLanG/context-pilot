"""Qt 键码 → 热键字符串的映射。

这是快捷键模块里**唯一依赖 Qt** 的部分，与 keys.py（纯逻辑）刻意分离：
Qt 的 Key_* 枚举与 Win32 虚拟键码的换算只在这里出现，其余层不碰 Qt 键码。

QML 层捕获按键后把 Qt 键码 + 修饰符传进来，这里转成规范字符串；窗口内快捷键
与全局热键共用这套转换（qt_key_sequence 供 settings_model / shortcut_controller
捕获时调用）。
"""

from PySide6.QtCore import Qt

from context_pilot.shortcuts.keys import (
    MOD_ALT,
    MOD_CONTROL,
    MOD_SHIFT,
    MOD_WIN,
    HotkeyParseError,
    format as format_hotkey,
)
from context_pilot.shortcuts.registry import NAKED_KEYS

__all__ = ["qt_key_sequence", "NAKED_KEYS"]

# 只按修饰键时还不构成热键（Key_Shift/Control/Meta/Alt 属 Qt::Key 专区）
_MODIFIER_KEYS: frozenset[int] = frozenset(
    {int(Qt.Key_Shift), int(Qt.Key_Control), int(Qt.Key_Meta), int(Qt.Key_Alt)}
)

# Qt 键码 → Win32 虚拟键码。
# 用 Qt 枚举常量而不是手写数值：Tab / Return / Escape 这类非字母键在 Qt 里用的是
# 0x0100xxxx 专区，**并不等于**它们的 ASCII 值（Key_Return 是 0x01000004 而非 0x0D）。
# 此前写成 0x0D 等 ASCII 值，导致 Ctrl+Enter / Ctrl+Tab 在按下时查不到键码，被判成
# 「无法识别」而永远捕获不到——这类 bug 只在按特定键时才暴露，很难联想到是表写错了。
# 字母与数字恰好与 ASCII 一致，照 range 生成即可。
_QT_TO_VK: dict[int, int] = {
    int(Qt.Key_Space): 0x20,
    int(Qt.Key_Tab): 0x09,
    int(Qt.Key_Backspace): 0x08,
    int(Qt.Key_Return): 0x0D,
    int(Qt.Key_Enter): 0x0D,  # 小键盘回车，与主键盘回车同一个虚拟键
    int(Qt.Key_Escape): 0x1B,
    int(Qt.Key_Insert): 0x2D,
    int(Qt.Key_Delete): 0x2E,
    int(Qt.Key_Home): 0x24,
    int(Qt.Key_End): 0x23,
    int(Qt.Key_PageUp): 0x21,
    int(Qt.Key_PageDown): 0x22,
    int(Qt.Key_Left): 0x25,
    int(Qt.Key_Up): 0x26,
    int(Qt.Key_Right): 0x27,
    int(Qt.Key_Down): 0x28,
}
for _c in range(0x41, 0x5B):  # A-Z
    _QT_TO_VK[_c] = _c
for _c in range(0x30, 0x3A):  # 0-9
    _QT_TO_VK[_c] = _c
for _n in range(1, 25):  # F1-F24
    _QT_TO_VK[int(Qt.Key_F1) + _n - 1] = 0x70 + _n - 1


def qt_key_sequence(
    qt_key: int, qt_modifiers: int, *, allow_naked: bool = False
) -> str:
    """QML 按键 → 热键字符串；不构成合法绑定时返回空串。

    ``allow_naked`` 决定是否接受「无修饰键」的单键：全局热键必须带修饰键
    （否则系统层面拦不住普通按键），而窗口内的「关闭」允许绑成 Esc——Esc
    不产生字符，不会跟打字冲突。
    """
    # Qt.KeyboardModifier 是 flag 类型，PySide6 上不能直接 int()，要取 .value
    mask = qt_modifiers
    modifiers = 0
    if mask & Qt.ControlModifier.value:
        modifiers |= MOD_CONTROL
    if mask & Qt.AltModifier.value:
        modifiers |= MOD_ALT
    if mask & Qt.ShiftModifier.value:
        modifiers |= MOD_SHIFT
    if mask & Qt.MetaModifier.value:
        modifiers |= MOD_WIN

    if qt_key in _MODIFIER_KEYS:
        return ""

    vk = _QT_TO_VK.get(qt_key)
    if vk is None:
        return ""
    try:
        sequence = format_hotkey(modifiers, vk)
    except HotkeyParseError:
        return ""

    # 无修饰键：只有 allow_naked 且落在白名单（Esc / F1-F12）才放行
    if modifiers == 0 and not (allow_naked and sequence in NAKED_KEYS):
        return ""
    return sequence
