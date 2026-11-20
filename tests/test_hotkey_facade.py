"""全局热键门面的平台分发与错误包装单测。

门面的立身之本：对外接口稳定（GlobalHotkey 的 pressed 信号 + register/rebind/
unregister），平台差异全部藏在 shortcuts/backends/<platform> 后端里。本测试锁两件事：

1. 平台分发：不同 sys.platform 选到正确的后端类。
2. 错误包装：后端抛的 UnsupportedPlatformError 一律转成 HotkeyRegistrationError，
   这样 ui/app.py 里现有的 `except HotkeyRegistrationError` 逻辑跨平台通用。
"""

import pytest

from context_pilot.shortcuts import global_hotkey as facade
from context_pilot.shortcuts.errors import HotkeyRegistrationError
from context_pilot.shortcuts.backends.macos import MacOSBackend
from context_pilot.shortcuts.backends.wayland import WaylandBackend
from context_pilot.shortcuts.backends.windows import WindowsBackend
from context_pilot.shortcuts.backends.x11 import X11Backend


@pytest.fixture(autouse=True)
def _no_real_qwidget(monkeypatch):
    """Windows 后端构造里 new 一个 QWidget 作宿主窗口，而 QWidget 需要 QApplication
    （conftest 只提供 QGuiApplication），在 offscreen 下会直接挂起。这里把它替换成
    一个无害的占位，让「分发选型」测试不必真正触碰 Win32 窗口。"""
    import context_pilot.shortcuts.backends.windows as win_mod

    class _FakeHost:
        # 模拟 QWidget：winId() 返回占位句柄；testAttribute/create 供 _hwnd()
        # 强制创建原生句柄的路径调用。这里直接返回 True 表示「已创建」。
        def winId(self):
            return 1

        def testAttribute(self, attr):
            return True

        def create(self):
            pass

    monkeypatch.setattr(win_mod, "QWidget", _FakeHost)


def test_win32_selects_windows_backend(monkeypatch):
    monkeypatch.setattr(facade.sys, "platform", "win32")
    assert isinstance(facade._detect_backend(None, 1), WindowsBackend)


def test_darwin_selects_macos_backend(monkeypatch):
    monkeypatch.setattr(facade.sys, "platform", "darwin")
    assert isinstance(facade._detect_backend(None, 1), MacOSBackend)


def test_linux_wayland_selects_wayland_backend(monkeypatch):
    monkeypatch.setattr(facade.sys, "platform", "linux")
    monkeypatch.setattr(
        facade.os, "environ",
        {"WAYLAND_DISPLAY": "wayland-0", "XDG_SESSION_TYPE": "wayland"},
    )
    assert isinstance(facade._detect_backend(None, 1), WaylandBackend)


def test_linux_x11_selects_x11_backend(monkeypatch):
    monkeypatch.setattr(facade.sys, "platform", "linux")
    monkeypatch.setattr(facade.os, "environ", {"DISPLAY": ":0"})
    assert isinstance(facade._detect_backend(None, 1), X11Backend)


def test_unsupported_backend_error_is_wrapped(monkeypatch, qt_app):
    """非 Windows 后端 register 抛 UnsupportedPlatformError，门面应转成
    HotkeyRegistrationError，让 app.py 的 except 分支照常工作。"""
    monkeypatch.setattr(facade.sys, "platform", "linux")
    monkeypatch.setattr(
        facade.os, "environ",
        {"WAYLAND_DISPLAY": "wayland-0", "XDG_SESSION_TYPE": "wayland"},
    )

    hotkey = facade.GlobalHotkey("ctrl+shift+e", hotkey_id=1)
    with pytest.raises(HotkeyRegistrationError):
        hotkey.register()


def test_illegal_sequence_raises_without_touching_backend(monkeypatch, qt_app):
    """序列非法应在解析阶段就报 HotkeyRegistrationError，后端完全不参与。"""
    monkeypatch.setattr(facade.sys, "platform", "linux")
    monkeypatch.setattr(facade.os, "environ", {"DISPLAY": ":0"})

    hotkey = facade.GlobalHotkey("e", hotkey_id=1)  # 无修饰键，非法
    with pytest.raises(HotkeyRegistrationError):
        hotkey.register()
    assert hotkey._backend is None  # 解析失败不该实例化后端


def test_windows_backend_rejects_zero_hwnd(monkeypatch):
    """宿主窗口句柄为 0 时，Windows 后端应在调 RegisterHotKey 前就报错，
    而不是把无效句柄交给系统（后者返回 ERROR_INVALID_HANDLE，语义更模糊）。"""
    import context_pilot.shortcuts.backends.windows as win_mod

    class _ZeroHost:
        def testAttribute(self, attr):
            return True

        def create(self):
            pass

        def winId(self):
            return 0

    monkeypatch.setattr(win_mod, "QWidget", _ZeroHost)
    backend = WindowsBackend(app=None, hotkey_id=1)

    with pytest.raises(HotkeyRegistrationError) as exc_info:
        backend.register(0x0002 | 0x4000, ord("E"), lambda: None)
    assert exc_info.value.occupied is False
    assert "句柄" in str(exc_info.value)
