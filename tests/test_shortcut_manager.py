"""ShortcutManager 统一编排入口的单测。

锁三件事：
1. 全局热键：register_global 登记并返回 GlobalHotkey，query/get 可取回，改绑、注销正确。
2. 注册失败仍登记：register 抛 HotkeyRegistrationError 时 name 仍在表里，可后续 rebind 重试。
3. 窗口内快捷键：set_inwindow_bindings 归一化、inwindow_sequences 展开 Enter/Return 变体、
   validate_inwindow 复用 registry 的冲突规则。
"""

import pytest

from context_pilot.shortcuts import ShortcutManager
from context_pilot.shortcuts.errors import HotkeyRegistrationError
from context_pilot.shortcuts.global_hotkey import GlobalHotkey


@pytest.fixture(autouse=True)
def _no_real_qwidget(monkeypatch):
    """Windows 后端构造里 new QWidget 作宿主窗口，QWidget 需要 QApplication
    （conftest 只提供 QGuiApplication），offscreen 下会挂起。替换为无害占位，
    让 register 只走到「句柄无效 → HotkeyRegistrationError」这条可控路径。"""
    import context_pilot.shortcuts.backends.windows as win_mod

    class _FakeHost:
        def testAttribute(self, attr):
            return True

        def create(self):
            pass

        def winId(self):
            return 0

    monkeypatch.setattr(win_mod, "QWidget", _FakeHost)


def test_register_returns_globalhotkey_and_query_get():
    m = ShortcutManager()
    # 句柄为 0 → register 抛 HotkeyRegistrationError，但 name 应已登记
    with pytest.raises(HotkeyRegistrationError):
        m.register_global("enhance", "ctrl+shift+e")

    assert isinstance(m.get_global("enhance"), GlobalHotkey)
    # 序列在注册前已落表，query 仍能取到意图序列
    assert m.query_global("enhance") == "ctrl+shift+e"
    assert m.query_global("nope") is None
    assert m.get_global("nope") is None


def test_register_global_connects_callback():
    m = ShortcutManager()
    fired = []
    # 用一个后端能成功的假环境难做，这里验证 callback 在 register 抛异常前已被 connect
    # （manager 在 register 之前就 connect，所以即便注册失败，槽也已就位）。
    with pytest.raises(HotkeyRegistrationError):
        m.register_global("enhance", "ctrl+shift+e", on_pressed=lambda: fired.append(1))
    # 手动触发 pressed 信号验证连接已建立
    m.get_global("enhance").pressed.emit()
    assert fired == [1]


def test_rebind_global_unknown_name_raises_keyerror():
    m = ShortcutManager()
    with pytest.raises(KeyError):
        m.rebind_global("missing", "ctrl+alt+x")


def test_unregister_all_clears_table():
    m = ShortcutManager()
    with pytest.raises(HotkeyRegistrationError):
        m.register_global("enhance", "ctrl+shift+e")
    m.unregister_all_globals()
    assert m.get_global("enhance") is None


def test_inwindow_bindings_and_sequences():
    m = ShortcutManager()
    m.set_inwindow_bindings({"enhance": "ctrl+enter", "close": "esc"})
    assert m.inwindow_bindings()["enhance"] == "ctrl+enter"
    # Enter 应展开出小键盘 Return 变体
    assert m.inwindow_sequences()["enhance"] == ["ctrl+enter", "ctrl+return"]
    assert m.inwindow_sequences()["close"] == ["esc"]


def test_set_inwindow_unknown_action_raises():
    m = ShortcutManager()
    with pytest.raises(ValueError):
        m.set_inwindow("nope", "ctrl+e")


def test_validate_inwindow_reports_conflicts_with_globals():
    m = ShortcutManager()
    with pytest.raises(HotkeyRegistrationError):
        m.register_global("enhance", "ctrl+shift+e")
    m.set_inwindow_bindings(
        {
            "enhance": "ctrl+shift+e",  # 与全局热键相同 → warning
            "rerun": "ctrl+r",
            "use": "ctrl+u",
            "close": "esc",
            "view_enhanced": "alt+e",
            "view_diff": "alt+d",
            "view_context": "alt+c",
        }
    )
    issues = m.validate_inwindow()
    warnings = [i for i in issues if i.level == "warning"]
    assert any("双触发" in i.message for i in warnings)
    assert not any(i.level == "error" for i in issues)


def test_rebind_failure_rolls_back_old_hotkey(monkeypatch, qt_app):
    """新热键占用/非法时回滚旧热键，避免两个都没生效却显示旧值。"""
    import context_pilot.shortcuts.global_hotkey as facade

    class _Backend:
        def __init__(self):
            self.registered = []
            self.fail_once = False

        def register(self, modifiers, vk, callback):
            if self.fail_once:
                self.fail_once = False
                raise HotkeyRegistrationError("热键已被占用", occupied=True)
            self.registered.append((modifiers, vk))

        def unregister(self):
            self.registered.clear()

    backends: list[_Backend] = []

    def _detect(_app, _hotkey_id):
        backend = _Backend()
        backends.append(backend)
        return backend

    monkeypatch.setattr(facade, "_detect_backend", _detect)

    manager = ShortcutManager()
    hotkey = manager.register_global("enhance", "ctrl+shift+e")
    backend = backends[0]
    assert len(backend.registered) == 1

    backend.fail_once = True
    with pytest.raises(HotkeyRegistrationError):
        manager.rebind_global("enhance", "ctrl+alt+x")

    assert hotkey.sequence == "ctrl+shift+e"
    assert len(backend.registered) == 1  # 旧热键已重新注册
