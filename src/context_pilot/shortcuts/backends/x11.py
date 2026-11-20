"""Linux X11 全局热键后端：占位实现。

未接入：X11 可用 Xlib 的 XGrabKey（ctypes 调 libX11），BadAccess 映射为键被占用。
当前版本 Windows 优先，此平台尚未实现，register 会抛出 UnsupportedPlatformError。
"""

from context_pilot.shortcuts.errors import UnsupportedPlatformError


class X11Backend:
    def __init__(self, app, hotkey_id: int = 1) -> None:
        self._app = app
        self._hotkey_id = hotkey_id
        self._registered = False

    @property
    def registered(self) -> bool:
        return self._registered

    def register(self, modifiers: int, vk: int, callback) -> None:
        raise UnsupportedPlatformError(
            "X11 全局热键尚未实现：需接入 Xlib XGrabKey"
        )

    def unregister(self) -> None:
        self._registered = False
