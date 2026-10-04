"""剪贴板读写。仅在用户主动操作时调用，避免覆盖用户内容。"""

from PySide6.QtGui import QGuiApplication


def read_clipboard_text() -> str:
    """读取剪贴板文本。剪贴板内容为图片等非文本时返回空串。"""
    return QGuiApplication.clipboard().text() or ""


def write_clipboard_text(text: str) -> None:
    QGuiApplication.clipboard().setText(text)
