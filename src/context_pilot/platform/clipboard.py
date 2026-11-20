"""剪贴板读写。

Windows 上直接走 Win32（OpenClipboard / GetClipboardData / SetClipboardData）。
**读不能用 Qt 的 QClipboard**：一旦本进程 setText/clear 过，Qt 就成了剪贴板
持有者并缓存自有内容；而抓取选中文本时主线程正阻塞在 sleep 里，来不及处理
系统广播把缓存失效，此时 ``clipboard().text()`` 会返回自己缓存的空串——
表现为「按键复制明明成功，却读到空文本」。Win32 每次直读系统剪贴板，
不受本进程缓存影响。

非 Windows 退回 Qt 实现。
"""

from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes

from PySide6.QtGui import QGuiApplication

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
_OPEN_RETRY = 8
_OPEN_RETRY_DELAY = 0.02


def _user32():
    """取带正确函数原型的 user32。

    句柄类返回值/参数必须显式声明，否则 ctypes 按 C int 处理：64 位下大句柄
    被截断，GlobalLock 拿到的指针就是错的（读到乱码或崩溃）。
    """
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    return user32


def _kernel32():
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.restype = wintypes.HGLOBAL
    return kernel32


def _open_clipboard(user32) -> bool:
    """打开剪贴板；被别的进程占用时短暂重试（剪贴板是全局互斥资源）。"""
    for _ in range(_OPEN_RETRY):
        if user32.OpenClipboard(None):
            return True
        time.sleep(_OPEN_RETRY_DELAY)
    return False


def _win32_read() -> str | None:
    """直接读系统剪贴板的文本；拿不到返回 None（区分「空文本」与「读失败」）。"""
    user32 = _user32()
    if not _open_clipboard(user32):
        return None
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""
        kernel32 = _kernel32()
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return None
        try:
            return ctypes.wstring_at(ptr)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def _win32_write(text: str) -> bool:
    """把文本写进系统剪贴板；成功返回 True。"""
    user32 = _user32()
    kernel32 = _kernel32()
    # SetClipboardData 要求 UTF-16 + 结尾 NUL
    payload = text.encode("utf-16-le") + b"\x00\x00"
    if not _open_clipboard(user32):
        return False
    handle = None
    try:
        if not user32.EmptyClipboard():
            return False
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(payload))
        if not handle:
            return False
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            kernel32.GlobalFree(handle)
            return False
        ctypes.memmove(ptr, payload, len(payload))
        kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            kernel32.GlobalFree(handle)
            return False
        handle = None  # 所有权已交给系统，不能再 free
        return True
    finally:
        if handle:
            kernel32.GlobalFree(handle)
        user32.CloseClipboard()


def _win32_clear() -> bool:
    user32 = _user32()
    if not _open_clipboard(user32):
        return False
    try:
        return bool(user32.EmptyClipboard())
    finally:
        user32.CloseClipboard()


def clipboard_sequence() -> int:
    """剪贴板变更序号：任何进程每次写入剪贴板，该序号都会递增。

    用它判断「Ctrl+C 到底有没有真的发生」，比「先清空剪贴板再读」安全得多
    —— 后者在复制失败时会把用户原有剪贴板弄丢，而这里完全不碰用户内容。
    """
    if sys.platform != "win32":
        return 0
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetClipboardSequenceNumber.restype = wintypes.DWORD
    return int(user32.GetClipboardSequenceNumber())


def read_clipboard_text() -> str:
    """读取剪贴板文本。剪贴板内容为图片等非文本时返回空串。"""
    if sys.platform == "win32":
        text = _win32_read()
        if text is not None:
            return text
        # Win32 打不开剪贴板时退回 Qt（至少还能拿到本进程自己的内容）
    return QGuiApplication.clipboard().text() or ""


def write_clipboard_text(text: str) -> None:
    if sys.platform == "win32" and _win32_write(text):
        return
    QGuiApplication.clipboard().setText(text)


def clear_clipboard() -> None:
    """清空剪贴板。

    抓取选中文本前用它：目标应用没有可复制内容时，剪贴板会保留上一次的旧
    内容，不清空就会把过期文本当成用户输入。**成功后本进程不再持有剪贴板**，
    后续由目标应用自己写入，Win32 直读即可拿到新内容。
    """
    if sys.platform == "win32" and _win32_clear():
        return
    clipboard = QGuiApplication.clipboard()
    if clipboard is not None:
        clipboard.clear()
