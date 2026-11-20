"""兼容转发：全局热键门面已迁至 context_pilot.shortcuts.global_hotkey。

保留此模块只为让历史 import 路径（``from context_pilot.platform.hotkey import ...``）
继续可用；新代码请直接使用 context_pilot.shortcuts。
"""

from context_pilot.shortcuts.errors import HotkeyRegistrationError, UnsupportedPlatformError
from context_pilot.shortcuts.global_hotkey import GlobalHotkey

__all__ = ["GlobalHotkey", "HotkeyRegistrationError", "UnsupportedPlatformError"]
