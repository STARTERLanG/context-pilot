"""设置页「窗口快捷键」分区的 QML 冒烟 + 控制器行为。

Python 侧的规则在 test_shortcuts.py 里锁，主窗口接线在 test_ui_shortcuts.py 里锁；
这里补最后一环：**设置页本身能不能正常装配、点了有没有反应**。三者缺一，用户
拿到的就是一个「改了不生效」或「一打开就报错」的面板。
"""

import os

import pytest

from PySide6.QtQuick import QQuickView  # noqa: E402

from context_pilot.core.shortcuts import ACTION_IDS  # noqa: E402
from context_pilot.ui.qml_setup import check, configure, source  # noqa: E402
from context_pilot.ui.session_controller import SessionController  # noqa: E402
from context_pilot.ui.settings_controller import SettingsController  # noqa: E402
from context_pilot.ui.settings_model import SettingsModel  # noqa: E402
from context_pilot.ui.shortcut_controller import ShortcutController  # noqa: E402


@pytest.fixture(scope="module")
def isolated_home(tmp_path_factory):
    home = tmp_path_factory.mktemp("home")
    old = os.environ.get("USERPROFILE"), os.environ.get("HOME")
    os.environ["USERPROFILE"] = str(home)
    os.environ["HOME"] = str(home)
    yield home
    for key, value in zip(("USERPROFILE", "HOME"), old):
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@pytest.fixture(scope="module")
def panel(qt_app, isolated_home):
    """装配「窗口快捷键」分区；QML 有错直接失败。"""
    settings = SettingsModel()
    ctl = ShortcutController(settings)

    view = QQuickView()
    configure(view)
    view.rootContext().setContextProperty("shortcut_ctl", ctl)
    view.setSource(source("settings/SettingsShortcuts.qml"))
    check(view, "SettingsShortcuts")
    qt_app.processEvents()
    return ctl, view.rootObject(), view


def _binding_fields(root) -> dict:
    """按 objectName 收集每个动作的绑定框。"""
    found: dict = {}
    stack = list(root.childItems())
    while stack:
        item = stack.pop()
        name = item.objectName()
        if name.startswith("bindingField_"):
            found[name[len("bindingField_"):]] = item
        stack.extend(item.childItems())
    return found


def test_every_action_has_a_field(panel):
    """七个动作都要有输入框——少一个就是有人加了动作忘了配 UI。"""
    _, root, _ = panel
    fields = _binding_fields(root)
    assert set(fields) == set(ACTION_IDS)


def test_fields_show_current_binding(panel, qt_app):
    """绑定框显示的是当前生效值，不是方案默认值也不是空串。"""
    ctl, root, _ = panel
    fields = _binding_fields(root)
    for row in ctl.actions:
        assert fields[row["id"]].property("display") == row["display"]
        assert fields[row["id"]].property("display")


def test_switch_scheme_updates_fields(panel, qt_app):
    """切方案后，界面上的每个框都跟着变（不是只改了下拉框的选中态）。"""
    ctl, root, _ = panel
    before = {k: v.property("display") for k, v in _binding_fields(root).items()}

    ctl.setScheme("alt")
    qt_app.processEvents()

    after = {k: v.property("display") for k, v in _binding_fields(root).items()}
    assert after != before
    assert after["enhance"] == "Alt+Enter"

    ctl.setScheme("balanced")
    qt_app.processEvents()


def test_invalid_capture_is_refused(panel, qt_app):
    """按下裸字母键不能被接受：控制器的捕获接口必须返回空串。"""
    ctl, _, _ = panel
    # Qt.Key_E (0x45) 且无修饰键
    assert ctl.capture("view_diff", 0x45, 0) == ""
    assert ctl.bindings["view_diff"] == "alt+d"


def test_valid_capture_rebinds(panel, qt_app):
    """Ctrl+Shift+D 应被接受，并即时反映在绑定表里。"""
    ctl, _, _ = panel
    from PySide6.QtCore import Qt

    # Qt.KeyboardModifier 是 flag 类型，PySide6 上不能直接 int()，要取 .value
    modifiers = Qt.ControlModifier.value | Qt.ShiftModifier.value
    assert ctl.capture("view_diff", Qt.Key_D.value, modifiers) == "ctrl+shift+d"
    assert ctl.bindings["view_diff"] == "ctrl+shift+d"

    ctl.resetAction("view_diff")
    assert ctl.bindings["view_diff"] == "alt+d"


def test_duplicate_capture_is_rejected_naming_the_other_action(panel, qt_app):
    """重复绑定要说清楚撞的是谁——只回一句「无效」，用户没法自己解决。"""
    from PySide6.QtCore import Qt

    ctl, _, _ = panel
    # 「视图 · 增强结果」当前是 alt+e；把「视图 · 差异」也绑成 alt+e
    assert ctl.capture("view_diff", Qt.Key_E.value, Qt.AltModifier.value) == ""
    assert "重复" in ctl.rejectReason
    assert "增强结果" in ctl.rejectReason
    # 被拒就必须保持原值，不能留下半改状态
    assert ctl.bindings["view_diff"] == "alt+d"


def test_edit_combo_capture_is_rejected(panel, qt_app):
    """抢复制/粘贴/撤销这类编辑组合要当场拦下并说明原因。"""
    from PySide6.QtCore import Qt

    ctl, _, _ = panel
    assert ctl.capture("use", Qt.Key_C.value, Qt.ControlModifier.value) == ""
    assert "文本编辑" in ctl.rejectReason
    assert ctl.bindings["use"] == "ctrl+u"


def test_close_accepts_naked_escape(panel, qt_app):
    """只有「关闭窗口」允许绑成裸 Esc——Esc 打不出字符，抢不了输入。"""
    from PySide6.QtCore import Qt

    ctl, _, _ = panel
    assert ctl.capture("close", Qt.Key_Escape.value, 0) == "esc"
    assert ctl.bindings["close"] == "esc"
    assert ctl.escIsClose is True

    # 换回组合键后，escIsClose 要跟着回落，否则两条 Esc 会同时关窗
    assert ctl.capture("close", Qt.Key_W.value, Qt.ControlModifier.value) == "ctrl+w"
    assert ctl.escIsClose is False

    ctl.resetAction("close")


def test_settings_page_assembles_with_new_tab(qt_app, isolated_home):
    """整页装配冒烟：加了第六个分类后，设置页本身不能变成空白或报错。

    SettingsShortcuts 是内联声明（非 Loader 懒加载），页面一实例化就会构建，
    所以这里能真正覆盖到它；QML 有错会由 check() 直接抛出来。
    """
    settings = SettingsModel()
    settings_ctl = SettingsController(settings)
    session_ctl = SessionController(settings.config)
    shortcut_ctl = ShortcutController(settings)
    try:
        view = QQuickView()
        configure(view)
        for name, obj in (
            ("settings", settings),
            ("settingsCtl", settings_ctl),
            ("sessionCtl", session_ctl),
            ("shortcut_ctl", shortcut_ctl),
        ):
            view.rootContext().setContextProperty(name, obj)
        view.setSource(source("settings/SettingsPage.qml"))
        check(view, "SettingsPage")
        qt_app.processEvents()

        root = view.rootObject()
        # QML 的 var 数组经 property() 回来是 QJSValue，要先转成 Python 序列
        tabs = [str(t) for t in root.property("tabs").toVariant()]
        assert "窗口快捷键" in tabs and "全局热键" in tabs

        # 切到最后一个分类，确认分区真的被构建出来了
        root.setProperty("currentTab", len(tabs) - 1)
        qt_app.processEvents()
        assert _binding_fields(root)
    finally:
        settings_ctl.shutdown()


def test_save_is_blocked_while_broken(isolated_home, qt_app):
    """绑定表有问题时，保存必须被拦下——否则用户会存进一份开不了窗的配置。"""
    settings = SettingsModel()
    ctl = ShortcutController(settings)

    failed = []
    settings.saveFailed.connect(failed.append)

    assert ctl.capture("use", 0x45, 0) == ""  # 裸键，未被写入
    # 直接注入非法值，模拟手改 toml 的场景
    settings.set_shortcut_binding("use", "u")
    assert settings.save() is False
    assert failed and "窗口快捷键" in failed[0]

    settings.set_shortcut_binding("use", "ctrl+u")
    assert settings.save() is True
