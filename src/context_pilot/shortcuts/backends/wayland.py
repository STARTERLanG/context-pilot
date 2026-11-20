"""Linux Wayland 全局热键后端：占位实现。

Wayland 出于安全禁止应用全局抓键，只能走 xdg-desktop-portal 的 GlobalShortcuts
接口（且通常依赖 GNOME/KDE 扩展）。此路径需要桌面环境配合，当前版本 Windows
优先，尚未实现，register 会抛出 UnsupportedPlatformError，并应由调用方降级到
「托盘 / 命令行唤起」的替代交互。
"""

from context_pilot.shortcuts.errors import UnsupportedPlatformError


class WaylandBackend:
    def __init__(self, app, hotkey_id: int = 1) -> None:
        self._app = app
        self._hotkey_id = hotkey_id
        self._registered = False

    @property
    def registered(self) -> bool:
        return self._registered

    def register(self, modifiers: int, vk: int, callback) -> None:
        raise UnsupportedPlatformError(
            "Wayland 不支持应用级全局热键：需通过桌面环境的 GlobalShortcuts portal 接入"
        )

    def unregister(self) -> None:
        self._registered = False
