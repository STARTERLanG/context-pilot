"""SettingsModel 单测（临时 HOME，不读用户真实配置）。

重点覆盖两件事：
- 「常规」四个预算与三个行为开关必须带 NOTIFY，否则 QML 侧的声明式绑定
  不会重新求值，且 Qt 会打 QQmlExpression「depends on non-bindable properties」警告；
- 写值是幂等的：值没变就不发信号，避免无谓的绑定重算。
"""

import pytest
from PySide6.QtCore import QCoreApplication

from context_pilot.ui.settings_model import SettingsModel

# QML 里以 `value: settings.xxx` / `checked: settings.xxx` 绑定的全部属性
BOUND_PROPERTIES = (
    "hotkey",
    "toggleHotkey",
    "maxTokens",
    "rulesTokens",
    "memoryTokens",
    "codeTokens",
    "autostart",
    "autoCopy",
    "closeToTray",
)


@pytest.fixture(scope="module")
def qapp():
    return QCoreApplication.instance() or QCoreApplication([])


@pytest.fixture
def isolated_home(monkeypatch, tmp_path):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def settings(qapp, isolated_home):
    return SettingsModel()


def _notify_name(prop: str) -> str:
    return prop[0].lower() + prop[1:] + "Changed"


@pytest.mark.parametrize("prop", BOUND_PROPERTIES)
def test_bound_property_has_notify(settings, prop):
    """缺失 NOTIFY 会让依赖它的 QML 绑定失效（Qt 也会打警告），必须拦截。"""
    meta = settings.metaObject()
    index = meta.indexOfProperty(prop)
    assert index >= 0, f"{prop} 不是 SettingsModel 的属性"
    notify = meta.property(index).notifySignal()
    assert notify.isValid(), f"{prop} 缺少 NOTIFY 信号（QML 绑定不会更新）"
    assert bytes(notify.name()).decode() == _notify_name(prop)


@pytest.mark.parametrize(
    "prop,value",
    [
        ("maxTokens", 12000),
        ("rulesTokens", 1500),
        ("memoryTokens", 900),
        ("codeTokens", 4000),
        ("autostart", True),
        ("autoCopy", False),
        ("closeToTray", True),
    ],
)
def test_set_value_updates_and_emits(settings, prop, value):
    signal = getattr(settings, _notify_name(prop))
    seen = []
    signal.connect(lambda *args: seen.append(True))

    original = getattr(settings, prop)
    setattr(settings, prop, value)
    assert getattr(settings, prop) == value
    # 写的是新值才发信号；写成当前值不发（幂等，避免绑定空转）
    if original != value:
        assert seen, f"{prop} 变化后未发 NOTIFY"
    setattr(settings, prop, value)
    assert getattr(settings, prop) == value
    emit_count = len(seen)
    setattr(settings, prop, value)
    assert len(seen) == emit_count, f"{prop} 写入相同值仍发了 NOTIFY"


def test_hotkey_properties_notify(settings):
    """两个热键原本就有 notify，这里一并锁住，防止重构时被删掉。"""
    for prop, value in (("hotkey", "ctrl+alt+j"), ("toggleHotkey", "ctrl+alt+k")):
        signal = getattr(settings, _notify_name(prop))
        seen = []
        signal.connect(lambda *a, _v=value: seen.append(_v))
        setattr(settings, prop, value)
        assert getattr(settings, prop) == value
        assert seen
