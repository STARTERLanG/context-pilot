"""Windows 全局热键：ctypes RegisterHotKey + Qt 原生事件过滤器。

选它而非键盘钩子库的原因：RegisterHotKey 由系统独占注册，热键被占用时可直接检测，
且 WM_HOTKEY 走 Qt 消息泵，回调天然在主线程。
"""

import ctypes
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal
from PySide6.QtWidgets import QApplication, QWidget

from context_pilot.platform.keys import MOD_NOREPEAT, format as format_hotkey, parse

# Win32 常量
WM_HOTKEY = 0x0312
ERROR_HOTKEY_ALREADY_REGISTERED = 1409

_HOTKEY_ID = 1
_NATIVE_MSG_TYPE = b"windows_generic_MSG"


class HotkeyRegistrationError(RuntimeError):
    """注册失败。occupied 为真表示组合键已被其他程序占用。"""

    def __init__(self, message: str, *, occupied: bool) -> None:
        super().__init__(message)
        self.occupied = occupied


class _HotkeyEventFilter(QAbstractNativeEventFilter):
    def __init__(self, on_pressed) -> None:
        super().__init__()
        self._on_pressed = on_pressed

    def nativeEventFilter(self, event_type, message):
        if event_type == _NATIVE_MSG_TYPE:
            msg = ctypes.cast(int(message), ctypes.POINTER(wintypes.MSG)).contents
            if msg.message == WM_HOTKEY and msg.wParam == _HOTKEY_ID:
                self._on_pressed()
                return True, 0
        return False, 0


class GlobalHotkey(QObject):
    """注册可配置的全局热键，按下时发出 pressed 信号。"""

    pressed = Signal()

    def __init__(self, sequence: str = "ctrl+shift+e", parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._sequence = sequence
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._filter = _HotkeyEventFilter(self.pressed.emit)
        # 宿主窗口常驻且不可见：热键需要稳定的原生窗口句柄，
        # 不能绑在会被销毁的预览窗上。不 show() 也会分配句柄。
        self._host = QWidget()
        self._registered = False
        self._active_sequence: str | None = None

    @property
    def sequence(self) -> str:
        return self._active_sequence or self._sequence

    def register(self, sequence: str | None = None) -> None:
        app = QApplication.instance()
        if app is None:
            raise RuntimeError("注册全局热键前必须先创建 QApplication")

        sequence = sequence or self._sequence
        try:
            modifiers, vk = parse(sequence)
        except ValueError as exc:
            raise HotkeyRegistrationError(
                f"热键 {sequence} 不合法：{exc}", occupied=False
            ) from exc

        hwnd = int(self._host.winId())
        ok = self._user32.RegisterHotKey(
            wintypes.HWND(hwnd),
            _HOTKEY_ID,
            modifiers | MOD_NOREPEAT,
            vk,
        )
        if not ok:
            error = ctypes.get_last_error()
            raise HotkeyRegistrationError(
                f"注册热键 {format_hotkey(modifiers, vk)} 失败（错误码 {error}）",
                occupied=(error == ERROR_HOTKEY_ALREADY_REGISTERED),
            )

        self._active_sequence = sequence
        self._registered = True
        app.installNativeEventFilter(self._filter)

    def rebind(self, sequence: str) -> None:
        """换一个热键：先注销旧的，再注册新的。失败时旧热键不再生效。"""
        self.unregister()
        self._sequence = sequence
        self.register(sequence)

    def unregister(self) -> None:
        if not self._registered:
            return
        app = QApplication.instance()
        if app is not None:
            app.removeNativeEventFilter(self._filter)
        self._user32.UnregisterHotKey(wintypes.HWND(int(self._host.winId())), _HOTKEY_ID)
        self._registered = False
