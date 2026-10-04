"""Windows 全局热键：ctypes RegisterHotKey + Qt 原生事件过滤器。

选它而非键盘钩子库的原因：RegisterHotKey 由系统独占注册，热键被占用时可直接检测，
且 WM_HOTKEY 走 Qt 消息泵，回调天然在主线程。
"""

import ctypes
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal
from PySide6.QtWidgets import QApplication, QWidget

# Win32 常量
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
VK_E = 0x45
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
    """注册 Ctrl+Shift+E 全局热键，按下时发出 pressed 信号。"""

    pressed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._filter = _HotkeyEventFilter(self.pressed.emit)
        # 宿主窗口常驻且不可见：热键需要稳定的原生窗口句柄，
        # 不能绑在会被销毁的预览窗上。不 show() 也会分配句柄。
        self._host = QWidget()
        self._registered = False

    def register(self) -> None:
        app = QApplication.instance()
        if app is None:
            raise RuntimeError("注册全局热键前必须先创建 QApplication")

        hwnd = int(self._host.winId())
        ok = self._user32.RegisterHotKey(
            wintypes.HWND(hwnd),
            _HOTKEY_ID,
            MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT,
            VK_E,
        )
        if not ok:
            error = ctypes.get_last_error()
            raise HotkeyRegistrationError(
                f"注册热键 Ctrl+Shift+E 失败（错误码 {error}）",
                occupied=(error == ERROR_HOTKEY_ALREADY_REGISTERED),
            )

        self._registered = True
        app.installNativeEventFilter(self._filter)

    def unregister(self) -> None:
        if not self._registered:
            return
        app = QApplication.instance()
        if app is not None:
            app.removeNativeEventFilter(self._filter)
        self._user32.UnregisterHotKey(wintypes.HWND(int(self._host.winId())), _HOTKEY_ID)
        self._registered = False
