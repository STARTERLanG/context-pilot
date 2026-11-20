"""全局热键后端的公共类型与抽象。

后端接口刻意保持最小：门面只依赖 register / unregister / registered，
其余（序列解析、pressed 信号、错误包装）都在门面层完成。这样新增平台
只需实现一个后端类，不必关心 Qt 生命周期与配置。
"""

from collections.abc import Callable
from typing import Protocol

from context_pilot.shortcuts.errors import (
    HotkeyRegistrationError,
    UnsupportedPlatformError,
)

__all__ = [
    "UnsupportedPlatformError",
    "HotkeyRegistrationError",
    "Backend",
]


class Backend(Protocol):
    """一个平台后端应实现的接口。

    register 失败时抛出 HotkeyRegistrationError（occupied 表示键被占用），
    由门面统一捕获并透传。回调在主线程 / 事件循环线程触发。
    """

    def register(self, modifiers: int, vk: int, callback: Callable[[], None]) -> None: ...

    def unregister(self) -> None: ...

    @property
    def registered(self) -> bool: ...
