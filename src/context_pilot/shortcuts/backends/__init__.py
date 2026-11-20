"""全局热键的平台后端。"""

from context_pilot.shortcuts.backends.base import (
    Backend,
    HotkeyRegistrationError,
    UnsupportedPlatformError,
)

__all__ = [
    "Backend",
    "HotkeyRegistrationError",
    "UnsupportedPlatformError",
]
