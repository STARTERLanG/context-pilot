"""快捷键模块的异常类型。

集中定义，避免各层各自 import 造成循环依赖：解析层抛 HotkeyParseError，
全局热键后端抛 HotkeyRegistrationError / UnsupportedPlatformError，其余模块
只从这里 import。
"""


class HotkeyParseError(ValueError):
    """热键字符串无法解析或不合法。"""


class UnsupportedPlatformError(RuntimeError):
    """当前平台没有可用的全局热键后端（如 Wayland）。"""


class HotkeyRegistrationError(RuntimeError):
    """注册失败。occupied 为真表示组合键已被其他程序占用。"""

    def __init__(self, message: str, *, occupied: bool) -> None:
        super().__init__(message)
        self.occupied = occupied
