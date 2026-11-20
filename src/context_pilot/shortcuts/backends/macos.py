"""macOS 全局热键后端：占位实现。

未接入：macOS 需用 Carbon 的 RegisterEventHotKey（ctypes 可调），且必须由用户
在「系统设置 → 隐私与安全性 → 辅助功能」中授权（AXIsProcessTrusted 检测）。
当前版本 Windows 优先，此平台尚未实现，register 会抛出 UnsupportedPlatformError，
避免静默失效误导用户。
"""

from context_pilot.shortcuts.errors import UnsupportedPlatformError


class MacOSBackend:
    def __init__(self, app, hotkey_id: int = 1) -> None:
        self._app = app
        self._hotkey_id = hotkey_id
        self._registered = False

    @property
    def registered(self) -> bool:
        return self._registered

    def register(self, modifiers: int, vk: int, callback) -> None:
        raise UnsupportedPlatformError(
            "macOS 全局热键尚未实现：需接入 Carbon RegisterEventHotKey 并引导用户授权辅助功能权限"
        )

    def unregister(self) -> None:
        self._registered = False
