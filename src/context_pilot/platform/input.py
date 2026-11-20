"""Windows 按键模拟与前景窗口切换。

全局增强热键的「全选 → 复制 → 增强 → 粘贴回写」链路用：读焦点窗口句柄、
模拟 Ctrl+A / Ctrl+C / Ctrl+V、把前景权还给目标窗口。仅在 Windows 生效，
非 Windows 一律 no-op（返回 False / None），调用方据此降级到「提示不支持」。

用 SendInput（而非已废弃的 keybd_event），对现代应用兼容性更好。
"""

from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes

__all__ = [
    "activate_window",
    "copy_selected",
    "copy_selected_only",
    "focused_control",
    "foreground_window",
    "grab_selected_text",
    "is_available",
    "paste_into_focused",
    "select_all",
    "select_all_copy",
    "window_title",
    "write_and_paste",
]

# SendInput 相关常量
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
VK_CONTROL = 0x11
VK_A = 0x41
VK_C = 0x43
VK_V = 0x56

# 组合键各事件之间的间隔：背靠背投递会导致目标窗口只拿到修饰键、丢掉字母键
_KEY_EVENT_GAP = 0.02

# 前景窗口相关
SW_RESTORE = 9
# 「前台锁定超时」：Windows 用它决定后台进程能否抢前台。临时置 0 即可解除
# 系统对我们（非前台进程）切换前台窗口的静默拒绝——这是回写能否成功的核心。
SPI_GETFOREGROUNDLOCKTIMEOUT = 0x2000
SPI_SETFOREGROUNDLOCKTIMEOUT = 0x2001
SPIF_SENDCHANGE = 0x0002


class _MOUSEINPUT(ctypes.Structure):
    """必须定义：INPUT 是「type + 最大成员」的联合体，最大成员是 MOUSEINPUT。

    少了它，联合体只按 KEYBDINPUT (24B) 算大小，_INPUT 会变成 32 字节，而
    64 位 Windows 上真实 INPUT 是 40 字节。SendInput 会校验
    cbSize == sizeof(INPUT)，尺寸不符就**直接返回 0**——表现是所有合成按键
    （Ctrl+A / Ctrl+C / Ctrl+V）全部静默失效。
    """

    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),  # ULONG_PTR
    ]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),  # ULONG_PTR
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT), ("hi", _HARDWAREINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", _INPUT_UNION)]


def is_available() -> bool:
    return sys.platform == "win32"


def _foreground_hwnd() -> int:
    """当前前台窗口句柄（0 表示没有）。

    必须显式把 restype 定为 HWND：ctypes 默认按 C int 解析返回值，64 位下
    句柄高位会被截断，导致「明明切过去了却判定失败」的假阴性。
    """
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetForegroundWindow.restype = wintypes.HWND
    hwnd = user32.GetForegroundWindow()
    return int(hwnd) if hwnd else 0


def foreground_window() -> int | None:
    """当前前台窗口句柄；非 Windows 返回 None。"""
    if not is_available():
        return None
    return _foreground_hwnd() or None


def window_title(hwnd: int | None) -> str:
    """取窗口标题（诊断用）；非 Windows 或取不到返回空串。"""
    if not is_available() or hwnd is None:
        return ""
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def _send_key(vk: int, keyup: bool) -> bool:
    """投递一次按键事件；返回 SendInput 是否真的接受了它。

    返回值很重要：目标窗口若运行在更高完整性级别（如以管理员身份运行），
    UIPI 会直接拦掉我们的合成输入，此时 SendInput 返回 0。据此如实报告失败，
    而不是谎报「已自动回写」。
    """
    if not is_available():
        return False
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.SendInput.argtypes = [
        wintypes.UINT,
        ctypes.POINTER(_INPUT),
        ctypes.c_int,
    ]
    user32.SendInput.restype = wintypes.UINT
    inp = _INPUT()
    inp.type = INPUT_KEYBOARD
    inp.union.ki = _KEYBDINPUT(
        wVk=vk,
        wScan=0,
        dwFlags=KEYEVENTF_KEYUP if keyup else 0,
        time=0,
        dwExtraInfo=0,
    )
    sent = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))
    return sent == 1


def _send_ctrl_combo(vk: int) -> bool:
    """模拟 Ctrl + 某键的一次完整按下/抬起；四个事件都投递成功才算成功。

    每个事件之间必须留一小段间隔：SendInput 是异步投递，四个事件背靠背塞进
    输入队列时，目标窗口常在一个消息循环里连收多条，修饰键状态尚未生效就
    收到字母键——实测表现为「Ctrl 到了、字母没到」，整组组合键失效。
    """
    if not is_available():
        return False
    results = []
    for code, keyup in (
        (VK_CONTROL, False),
        (vk, False),
        (vk, True),
        (VK_CONTROL, True),
    ):
        results.append(_send_key(code, keyup))
        time.sleep(_KEY_EVENT_GAP)
    return all(results)


def select_all() -> None:
    """模拟 Ctrl+A 全选当前焦点控件内容。"""
    _send_ctrl_combo(VK_A)


def copy_selected() -> None:
    """模拟 Ctrl+C 复制当前选中内容到剪贴板。"""
    _send_ctrl_combo(VK_C)


def copy_selected_only() -> None:
    """只复制已选中内容（Ctrl+C），不做全选。

    供「用户已手动全选」的场景使用：按下热键时文本已处于选中态，这里只需
    把选中内容放进剪贴板。留足间隔并让事件循环处理剪贴板更新。
    """
    from PySide6.QtWidgets import QApplication

    copy_selected()
    time.sleep(0.12)
    app = QApplication.instance()
    if app is not None:
        app.processEvents()


def select_all_copy() -> None:
    """全选 + 复制：把焦点控件里的全部文本放进剪贴板。

    复制前先清空剪贴板：目标应用没有可复制内容时（或按键没落地），否则会读到
    **上一次残留的旧文本**，把过期内容当成用户输入送去增强。清空后若仍为空，
    上层就能如实判断「没抓到文本」。

    每次模拟之间留足间隔，并让事件循环处理剪贴板更新，避免「复制还没完成
    就读剪贴板」拿到空值。
    """
    from PySide6.QtWidgets import QApplication

    from context_pilot.platform.clipboard import clear_clipboard

    app = QApplication.instance()
    clear_clipboard()
    if app is not None:
        app.processEvents()

    select_all()
    time.sleep(0.08)
    copy_selected()
    time.sleep(0.12)
    if app is not None:
        app.processEvents()


def grab_selected_text(*, select_all_first: bool) -> str | None:
    """抓取当前焦点控件里选中的文本；没抓到返回 None。

    select_all_first=True 时先 Ctrl+A 全选再复制（「自动复制粘贴」模式）；
    False 时只复制用户已手动选中的内容。

    成败判定用「剪贴板变更序号」而不是「先清空剪贴板再看有没有内容」：
    清空会把用户原有剪贴板弄丢，一旦复制失败就收不回来；序号方案只在复制
    真的发生时读取，复制没发生则原样不动，用户剪贴板毫发无损。
    """
    from context_pilot.platform.clipboard import (
        clipboard_sequence,
        read_clipboard_text,
    )

    if not is_available():
        return None

    seq_before = clipboard_sequence()

    if select_all_first:
        select_all()
        time.sleep(0.08)
    copy_selected()
    time.sleep(0.15)

    if clipboard_sequence() == seq_before:
        # 序号没变 = 目标没写剪贴板 = 复制没发生（无焦点 / 无选中 / 输入框为空）
        return None
    return read_clipboard_text()


def _user32():
    """取带正确函数原型的 user32。

    句柄类参数必须显式声明为 HWND：ctypes 默认把 Python int 按 C int 传递，
    64 位下大句柄会被截断，切前台就会莫名失败。
    """
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.c_void_p]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
    for name in (
        "IsWindow",
        "IsIconic",
        "BringWindowToTop",
        "SetForegroundWindow",
        "SetFocus",
    ):
        getattr(user32, name).argtypes = [wintypes.HWND]
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    return user32


def _set_foreground_lock_timeout(value: int | None = None) -> int | None:
    """读写「前台锁定超时」。

    value=None 表示只读取（返回当前值）。value 为整数时写入并返回旧值，供
    调用方稍后还原——临时置 0 是让后台进程能切前台的关键，办完事必须还原，
    否则会改变用户系统的窗口激活行为。
    """
    if not is_available():
        return None
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    old = wintypes.DWORD()
    if not user32.SystemParametersInfoW(
        SPI_GETFOREGROUNDLOCKTIMEOUT, 0, ctypes.byref(old), 0
    ):
        return None
    if value is None:
        return int(old.value)
    new = wintypes.DWORD(value)
    user32.SystemParametersInfoW(
        SPI_SETFOREGROUNDLOCKTIMEOUT, 0, ctypes.byref(new), SPIF_SENDCHANGE
    )
    return int(old.value)


def activate_window(hwnd: int | None, focus: int | None = None) -> bool:
    """强制把目标窗口切到前台，并把焦点还给它的编辑控件；返回是否真的切过去了。

    为什么不能只调 SetForegroundWindow：Windows 只允许「当前前台进程」或
    「最近一次输入事件来自本进程」的进程切换前台。热键触发时最后输入落在
    目标应用上，所以我们这个后台进程调用会被**静默拒绝**（返回 True 但窗口
    没变），从前「日志说激活成功、实际没回写」的怪象就是这么来的。

    这里用业界通行的组合拳：
      1. 临时把前台锁定超时置 0（解除系统拒绝），办完还原；
      2. 把当前线程同时 AttachThreadInput 到「目标线程」和「当前前台线程」——
         只附加目标线程是不够的，系统检查的是前台线程的输入队列；
      3. BringWindowToTop + SetForegroundWindow + SetFocus(焦点控件)；
      4. 最后用 GetForegroundWindow 复核，没切过去就如实返回 False。
    """
    if not is_available() or hwnd is None:
        return False
    user32 = _user32()
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    target = int(hwnd)

    if not user32.IsWindow(wintypes.HWND(target)):
        return False
    if user32.IsIconic(wintypes.HWND(target)):
        user32.ShowWindow(wintypes.HWND(target), SW_RESTORE)
    if _foreground_hwnd() == target:
        # 已经在前台：只需把焦点还回编辑控件
        if focus:
            user32.SetFocus(wintypes.HWND(focus))
        return True

    current_thread = kernel32.GetCurrentThreadId()
    target_thread = user32.GetWindowThreadProcessId(wintypes.HWND(target), None)
    foreground = _foreground_hwnd()
    foreground_thread = (
        user32.GetWindowThreadProcessId(wintypes.HWND(foreground), None)
        if foreground
        else 0
    )
    threads = {
        t for t in (target_thread, foreground_thread) if t and t != current_thread
    }

    attached: list[int] = []
    for thread in threads:
        if user32.AttachThreadInput(current_thread, thread, True):
            attached.append(thread)

    old_timeout = _set_foreground_lock_timeout(0)
    try:
        user32.BringWindowToTop(wintypes.HWND(target))
        user32.SetForegroundWindow(wintypes.HWND(target))
        if focus:
            user32.SetFocus(wintypes.HWND(focus))
    finally:
        if old_timeout is not None:
            _set_foreground_lock_timeout(old_timeout)
        for thread in attached:
            user32.AttachThreadInput(current_thread, thread, False)

    return _foreground_hwnd() == target


def paste_into_focused() -> bool:
    """向当前焦点控件粘贴剪贴板内容（Ctrl+V）；返回按键是否投递成功。"""
    if not is_available():
        return False
    return _send_ctrl_combo(VK_V)


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class _GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", _RECT),
    ]


def focused_control(hwnd: int | None = None) -> int | None:
    """取目标窗口所属线程中当前持有焦点的控件句柄（通常是编辑框）。

    只认 GetGUIThreadInfo：它返回的是**目标窗口线程**的焦点控件。不能用
    GetFocus 兜底——那返回的是调用线程自己的焦点窗口，跟目标窗口毫无关系。
    """
    if not is_available():
        return None
    user32 = _user32()

    if hwnd is None:
        hwnd = _foreground_hwnd()
    if not hwnd:
        return None

    thread = user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), None)
    info = _GUITHREADINFO()
    info.cbSize = ctypes.sizeof(_GUITHREADINFO)
    if thread and user32.GetGUIThreadInfo(thread, ctypes.byref(info)):
        return int(info.hwndFocus) if info.hwndFocus else None
    return None


def write_and_paste(hwnd: int | None, text: str, focus: int | None = None) -> bool:
    """把文本写入剪贴板并粘贴回目标窗口。

    focus 是抓取文本那一刻记录下的焦点控件句柄：增强耗时数秒，期间目标窗口
    内部的焦点可能已转移，回写时把它还回去，粘贴才会落到原来那个输入框。

    返回 True 仅当「确实把目标窗口切到前台、且 Ctrl+V 按键事件投递成功」。
    任何一环不成立都返回 False，由上层降级为「剪贴板 + 提示手动粘贴」——
    绝不在无法确认前台的情况下盲发 Ctrl+V（那会粘贴到别的窗口里去）。
    剪贴板无论如何都保留增强结果，不会丢。
    """
    from context_pilot.platform.clipboard import write_clipboard_text

    if not is_available() or not text:
        return False
    write_clipboard_text(text)

    # 焦点控件可能属于目标线程：SetFocus 要求调用线程与目标线程共享输入队列，
    # activate_window 内部已做 AttachThreadInput，故把 focus 一并传进去。
    if focus is None:
        focus = focused_control(hwnd)

    if not activate_window(hwnd, focus):
        return False

    # 给目标窗口一点时间处理 WM_ACTIVATE / 恢复插入符
    time.sleep(0.06)
    if foreground_window() != int(hwnd):
        return False
    return paste_into_focused()
