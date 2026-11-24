"""platform/input.py 的单元测试。

这是纯 Windows 能力（SendInput 模拟按键、GetForegroundWindow/SetForegroundWindow），
测试聚焦在可跨平台验证的部分：非 Windows 降级、no-op 行为、空文本参数处理。
底层真实 Win32 调用不在此覆盖（需真实桌面环境）。
"""

import sys

import pytest

from context_pilot.platform import input as input_mod


def test_is_available_false_on_non_windows(monkeypatch):
    monkeypatch.setattr(input_mod.sys, "platform", "linux")
    assert input_mod.is_available() is False


def test_foreground_window_none_on_non_windows(monkeypatch):
    monkeypatch.setattr(input_mod.sys, "platform", "linux")
    assert input_mod.foreground_window() is None


def test_select_all_copy_noop_on_non_windows(monkeypatch):
    monkeypatch.setattr(input_mod.sys, "platform", "linux")
    # 不应抛异常，直接返回
    input_mod.select_all_copy()
    input_mod.copy_selected_only()
    input_mod.select_all()
    input_mod.copy_selected()


def test_paste_into_focused_false_on_non_windows(monkeypatch):
    monkeypatch.setattr(input_mod.sys, "platform", "linux")
    assert input_mod.paste_into_focused() is False


def test_activate_window_false_on_non_windows(monkeypatch):
    monkeypatch.setattr(input_mod.sys, "platform", "linux")
    assert input_mod.activate_window(12345) is False


def test_write_and_paste_noop_on_non_windows(monkeypatch):
    monkeypatch.setattr(input_mod.sys, "platform", "linux")
    assert input_mod.write_and_paste(None, "hello") is False


def test_write_and_paste_noop_on_empty_text(monkeypatch):
    monkeypatch.setattr(input_mod.sys, "platform", "win32")
    assert input_mod.write_and_paste(None, "") is False


def test_focused_control_none_on_non_windows(monkeypatch):
    monkeypatch.setattr(input_mod.sys, "platform", "linux")
    assert input_mod.focused_control() is None


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Win32 结构体布局仅在 Windows 有意义，ctypes 在其他平台按本地 ABI 对齐",
)
def test_input_struct_size_matches_win32_layout():
    """`_INPUT` 的尺寸必须与系统一致，否则 SendInput 全部失效。

    SendInput 会校验 cbSize == sizeof(INPUT)：尺寸不符时它**直接返回 0**，
    一个按键都不会注入，而且不抛异常。曾经这里漏定义 MOUSEINPUT，联合体只
    按 KEYBDINPUT 算，整个 _INPUT 只有 32 字节（真实 x64 是 40），导致
    Ctrl+A / Ctrl+C / Ctrl+V 全部静默失效——抓取靠剪贴板旧内容"碰巧"成功，
    回写则永远失败。这个尺寸是硬约束，必须用测试钉死。
    """
    import ctypes

    pointer = ctypes.sizeof(ctypes.c_void_p)
    expected = 40 if pointer == 8 else 28
    assert ctypes.sizeof(input_mod._INPUT) == expected
    # KEYBDINPUT：2+2+4+4+ULONG_PTR（x64 下 padded 到 24）
    assert ctypes.sizeof(input_mod._KEYBDINPUT) == (24 if pointer == 8 else 16)
    # MOUSEINPUT 是联合体中最大的成员，INPUT 的大小由它决定
    assert ctypes.sizeof(input_mod._MOUSEINPUT) == (32 if pointer == 8 else 24)


def test_send_ctrl_combo_false_on_non_windows(monkeypatch):
    monkeypatch.setattr(input_mod.sys, "platform", "linux")
    assert input_mod._send_ctrl_combo(input_mod.VK_V) is False


def test_write_and_paste_keeps_clipboard_but_sends_no_key_when_activation_fails(
    monkeypatch,
):
    """切前台失败时绝不盲发 Ctrl+V（否则会粘贴到别的窗口），但结果不能丢。

    这是「很多窗口回写失败」的收口行为：宁可退化成「请手动 Ctrl+V」，
    也不要往错误窗口里乱贴。
    """
    monkeypatch.setattr(input_mod, "is_available", lambda: True)
    monkeypatch.setattr(input_mod, "focused_control", lambda hwnd=None: None)
    monkeypatch.setattr(input_mod, "activate_window", lambda hwnd, focus=None: False)
    sent: list[int] = []
    monkeypatch.setattr(
        input_mod, "paste_into_focused", lambda: sent.append(1) or True
    )
    writes: list[str] = []
    monkeypatch.setattr(
        "context_pilot.platform.clipboard.write_clipboard_text",
        lambda text: writes.append(text),
    )

    assert input_mod.write_and_paste(999, "增强后的文本") is False
    assert writes == ["增强后的文本"]  # 剪贴板兜底，结果不丢
    assert sent == []  # 但绝不盲发按键


def test_write_and_paste_sends_key_only_after_foreground_verified(monkeypatch):
    """激活函数自称成功也要复核前台：复核不过就不发按键。"""
    monkeypatch.setattr(input_mod, "is_available", lambda: True)
    monkeypatch.setattr(input_mod, "focused_control", lambda hwnd=None: 42)
    monkeypatch.setattr(input_mod, "activate_window", lambda hwnd, focus=None: True)
    monkeypatch.setattr(input_mod, "foreground_window", lambda: 0)
    sent: list[int] = []
    monkeypatch.setattr(
        input_mod, "paste_into_focused", lambda: sent.append(1) or True
    )
    monkeypatch.setattr(
        "context_pilot.platform.clipboard.write_clipboard_text", lambda text: None
    )

    assert input_mod.write_and_paste(999, "x") is False
    assert sent == []


def test_grab_selected_text_none_on_non_windows(monkeypatch):
    monkeypatch.setattr(input_mod.sys, "platform", "linux")
    assert input_mod.grab_selected_text(select_all_first=True) is None


def _stub_key_simulation(monkeypatch) -> None:
    """把真实按键注入打桩，测试只关心判定逻辑。"""
    monkeypatch.setattr(input_mod, "is_available", lambda: True)
    monkeypatch.setattr(input_mod, "select_all", lambda: None)
    monkeypatch.setattr(input_mod, "copy_selected", lambda: None)
    monkeypatch.setattr(input_mod.time, "sleep", lambda _seconds: None)


def test_grab_selected_text_none_when_clipboard_untouched(monkeypatch):
    """剪贴板序号没变 = 复制没发生，返回 None 且不碰用户剪贴板。

    判定靠序号而不是「先清空剪贴板再看有没有内容」：后者在复制失败时会把
    用户原有剪贴板弄丢，而按一次热键不该有这种副作用。
    """
    _stub_key_simulation(monkeypatch)
    from context_pilot.platform import clipboard as clipboard_mod

    monkeypatch.setattr(clipboard_mod, "clipboard_sequence", lambda: 7)
    monkeypatch.setattr(
        clipboard_mod, "read_clipboard_text", lambda: "不应被读到"
    )

    assert input_mod.grab_selected_text(select_all_first=True) is None


def test_grab_selected_text_reads_after_clipboard_changed(monkeypatch):
    """序号变化说明 Ctrl+C 真的落地，此时才去读剪贴板。"""
    _stub_key_simulation(monkeypatch)
    from context_pilot.platform import clipboard as clipboard_mod

    seqs = iter([1, 2])
    monkeypatch.setattr(clipboard_mod, "clipboard_sequence", lambda: next(seqs))
    monkeypatch.setattr(
        clipboard_mod, "read_clipboard_text", lambda: "抓到的选中文本"
    )

    assert input_mod.grab_selected_text(select_all_first=True) == "抓到的选中文本"
