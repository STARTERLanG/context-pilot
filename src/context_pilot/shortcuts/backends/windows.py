"""Windows 全局热键后端：ctypes RegisterHotKey + Qt 原生事件过滤器。

选它而非键盘钩子库的原因：RegisterHotKey 由系统独占注册，热键被占用时可直接检测，
且 WM_HOTKEY 走 Qt 消息泵，回调天然在主线程。

后端只持有「宿主窗口 + 原生过滤器」，不做序列解析：register 收到的 modifiers/vk
已由门面解析完成，本后端直接消费。
"""

import ctypes

from PySide6.QtCore import QAbstractNativeEventFilter, Qt
from PySide6.QtWidgets import QWidget

from context_pilot.shortcuts.errors import HotkeyRegistrationError

# Win32 常量
WM_HOTKEY = 0x0312
ERROR_HOTKEY_ALREADY_REGISTERED = 1409
ERROR_INVALID_HANDLE = 1400

_NATIVE_MSG_TYPE = b"windows_generic_MSG"


class _HotkeyEventFilter(QAbstractNativeEventFilter):
    """按 hotkey_id 过滤 WM_HOTKEY：同一进程内的多个注册共用同一个消息泵。"""

    def __init__(self, on_pressed, hotkey_id: int) -> None:
        super().__init__()
        self._on_pressed = on_pressed
        self._hotkey_id = hotkey_id

    def nativeEventFilter(self, event_type, message):
        if event_type == _NATIVE_MSG_TYPE:
            from ctypes import wintypes

            msg = ctypes.cast(int(message), ctypes.POINTER(wintypes.MSG)).contents
            if msg.message == WM_HOTKEY and msg.wParam == self._hotkey_id:
                self._on_pressed()
                return True, 0
        return False, 0


class WindowsBackend:
    """把「已解析的修饰符 + 虚拟键码」注册为系统级全局热键。"""

    def __init__(self, app, hotkey_id: int = 1) -> None:
        """app 为 QApplication 实例；hotkey_id 区分同一进程内的多个注册。"""
        self._app = app
        self._hotkey_id = hotkey_id
        # 延迟到真正注册/注销时才取 user32：构造阶段不该触碰 Win32 API，
        # 否则非 Windows 上的平台分发测试（CI 在 Ubuntu）会在实例化时崩溃。
        self._user32 = None
        self._wintypes = None
        self._filter: _HotkeyEventFilter | None = None
        # 宿主窗口常驻且不可见：热键需要稳定的原生窗口句柄，
        # 不能绑在会被销毁的预览窗上。不 show() 也会分配句柄。
        self._host = QWidget()
        self._registered = False

    @property
    def registered(self) -> bool:
        return self._registered

    def _api(self):
        """按需取 user32，避免在非 Windows 平台构造后端时加载 Win32 DLL。"""
        if self._user32 is None:
            from ctypes import wintypes

            self._wintypes = wintypes
            self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        return self._user32

    def _hwnd(self) -> int:
        """宿主窗口的原生句柄，必要时强制创建。

        QWidget 的原生句柄是惰性创建的：未显示过的窗口 winId() 可能返回
        0 或无效值（offscreen 平台返回占位 1），导致 RegisterHotKey 报
        ERROR_INVALID_HANDLE(1400)。create() 强制立即创建原生窗口，确保
        拿到真实可用的 HWND。
        """
        if not self._host.testAttribute(Qt.WidgetAttribute.WA_WState_Created):
            self._host.create()
        return int(self._host.winId())

    def register(self, modifiers: int, vk: int, callback) -> None:
        if self._registered:
            self.unregister()

        self._filter = _HotkeyEventFilter(callback, self._hotkey_id)

        hwnd = self._hwnd()
        if not hwnd:
            raise HotkeyRegistrationError(
                "宿主窗口句柄无效，无法注册热键", occupied=False
            )
        ok = self._api().RegisterHotKey(
            self._wintypes.HWND(hwnd),
            self._hotkey_id,
            modifiers,
            vk,
        )
        if not ok:
            error = ctypes.get_last_error()
            if error == ERROR_INVALID_HANDLE:
                raise HotkeyRegistrationError(
                    "宿主窗口句柄无效，无法注册热键", occupied=False
                )
            raise HotkeyRegistrationError(
                f"注册热键失败（错误码 {error}）",
                occupied=(error == ERROR_HOTKEY_ALREADY_REGISTERED),
            )

        self._registered = True
        self._app.installNativeEventFilter(self._filter)

    def unregister(self) -> None:
        if not self._registered:
            return
        if self._filter is not None:
            self._app.removeNativeEventFilter(self._filter)
        self._api().UnregisterHotKey(
            self._wintypes.HWND(int(self._host.winId())), self._hotkey_id
        )
        self._filter = None
        self._registered = False
