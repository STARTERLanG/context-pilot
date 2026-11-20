"""全局热键门面：按平台选择后端，对外暴露稳定的 GlobalHotkey 接口。

这里是「平台无关」的唯一入口：调用方（ui/app.py）只依赖本模块的
GlobalHotkey，不感知底层是 Win32 RegisterHotKey、Carbon 还是 XGrabKey。

职责拆分：
- 序列解析（字符串 → 平台修饰符/键码）：由本包的 keys.py 完成。
- 平台注册：由 backends/<platform>.py 的后端完成。
- 错误包装：后端抛出的异常统一转成 HotkeyRegistrationError 透传给调用方。

选 RegisterHotKey 而非键盘钩子库的原因：RegisterHotKey 由系统独占注册，
热键被占用时可直接检测，且 WM_HOTKEY 走 Qt 消息泵，回调天然在主线程。
"""

import os
import sys

from PySide6.QtCore import QObject, Signal

from context_pilot.shortcuts.errors import (
    HotkeyRegistrationError,
    UnsupportedPlatformError,
)
from context_pilot.shortcuts.keys import MOD_NOREPEAT, parse

__all__ = ["GlobalHotkey", "HotkeyRegistrationError", "UnsupportedPlatformError"]


def _session_is_wayland() -> bool:
    """通过环境变量判断是否运行在 Wayland 会话。"""
    if not sys.platform.startswith("linux"):
        return False
    if "WAYLAND_DISPLAY" not in os.environ:
        return False
    return os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"


def _detect_backend(app, hotkey_id: int):
    """按平台构造后端。非 Windows 后端目前为占位实现，实例化成功但 register 会报错。"""
    if sys.platform == "win32":
        from context_pilot.shortcuts.backends.windows import WindowsBackend

        return WindowsBackend(app, hotkey_id)
    if sys.platform == "darwin":
        from context_pilot.shortcuts.backends.macos import MacOSBackend

        return MacOSBackend(app, hotkey_id)
    if sys.platform.startswith("linux"):
        if _session_is_wayland():
            from context_pilot.shortcuts.backends.wayland import WaylandBackend

            return WaylandBackend(app, hotkey_id)
        from context_pilot.shortcuts.backends.x11 import X11Backend

        return X11Backend(app, hotkey_id)

    # 未知平台：给一个必然报「不支持」的后端，避免静默失效
    class _NullBackend:
        registered = False

        def register(self, modifiers, vk, callback):
            raise UnsupportedPlatformError(f"不支持的操作系统平台：{sys.platform}")

        def unregister(self):
            self.registered = False

    return _NullBackend()


class GlobalHotkey(QObject):
    """注册可配置的全局热键，按下时发出 pressed 信号。"""

    pressed = Signal()

    def __init__(
        self,
        sequence: str = "ctrl+shift+e",
        parent: QObject | None = None,
        *,
        hotkey_id: int = 1,
    ) -> None:
        """hotkey_id 区分同一进程内的多个热键，必须互不相同。"""
        super().__init__(parent)
        self._sequence = sequence
        self._hotkey_id = hotkey_id
        self._registered = False
        self._active_sequence: str | None = None
        # 后端在 register 时才需要 QApplication，这里只记录，不实例化后端——
        # 避免在非 Windows 平台一实例化就触碰 Win32 专有 API。
        self._backend = None

    @property
    def sequence(self) -> str:
        return self._active_sequence or self._sequence

    def register(self, sequence: str | None = None) -> None:
        from PySide6.QtWidgets import QApplication

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

        if self._backend is None:
            self._backend = _detect_backend(app, self._hotkey_id)

        # Windows 端需要 MOD_NOREPEAT 避免按住重复触发；其余平台忽略该位。
        modifiers |= MOD_NOREPEAT
        try:
            self._backend.register(modifiers, vk, self.pressed.emit)
        except UnsupportedPlatformError as exc:
            raise HotkeyRegistrationError(
                f"当前平台暂不支持全局热键：{exc}", occupied=False
            ) from exc

        self._active_sequence = sequence
        self._registered = True

    def rebind(self, sequence: str) -> None:
        """换一个热键：先注销旧的，再注册新的。

        新序列非法或被占用时回滚到旧热键——否则系统里两个热键都没生效，
        ``sequence`` 却还报旧值，调用方与用户都无法从状态看出异常。
        """
        previous = self._active_sequence or self._sequence
        was_registered = self._registered
        self.unregister()
        self._sequence = sequence
        try:
            self.register(sequence)
        except Exception:
            self._sequence = previous
            if was_registered:
                try:
                    self.register(previous)
                except Exception:
                    # 回滚也失败时如实清空生效态，不谎报旧热键仍在运行
                    self._registered = False
                    self._active_sequence = None
            raise

    def unregister(self) -> None:
        if not self._registered:
            return
        if self._backend is not None:
            self._backend.unregister()
        self._registered = False
