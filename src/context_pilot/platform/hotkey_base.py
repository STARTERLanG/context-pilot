"""兼容转发：全局热键后端抽象已迁至 context_pilot.shortcuts.backends.base。

保留此模块只为让历史 import 路径继续可用；新代码请直接使用
context_pilot.shortcuts.backends。
"""

from context_pilot.shortcuts.backends.base import (
    Backend,
    HotkeyRegistrationError,
    UnsupportedPlatformError,
)

__all__ = ["Backend", "HotkeyRegistrationError", "UnsupportedPlatformError"]
