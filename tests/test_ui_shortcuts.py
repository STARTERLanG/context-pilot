"""QML 主页面冒烟：快捷键装配与「禁单字母键」这条硬约束。

这是项目里第一份 QML 自动化测试。放在这里的原因很具体：窗口内快捷键
（PRD 三十一章）是纯 QML 实现，Python 侧测不到；而它的失败模式又很隐蔽
——删掉一个 Shortcut、或把组合键改回单字母，功能照常"看起来没问题"，
只是打字时会莫名跳视图。这种回归只能靠 QML 层断言守住。

用 QQuickView + offscreen 实例化，需要 QGuiApplication（不能复用 QCoreApplication）。
"""

import pytest

from PySide6.QtCore import Property, QObject, Slot  # noqa: E402
from PySide6.QtQuick import QQuickView  # noqa: E402

from context_pilot.core.models import EnhancedPrompt  # noqa: E402
from context_pilot.core.shortcuts import (  # noqa: E402
    ACTION_IDS,
    conflicts_with_typing,
)
from context_pilot.ui.preview_model import PreviewModel  # noqa: E402
from context_pilot.ui.qml_setup import check, configure, source  # noqa: E402
from context_pilot.ui.settings_model import SettingsModel  # noqa: E402
from context_pilot.ui.shortcut_controller import ShortcutController  # noqa: E402


class _WindowCtlStub(QObject):
    """替代真实的窗口控制器：只提供 QML 需要的接口，并记录 close 调用。"""

    def __init__(self) -> None:
        super().__init__()
        self.closed = False

    @Property(bool)
    def isMaximized(self) -> bool:
        return False

    @Slot()
    def close(self) -> None:
        self.closed = True

    @Slot()
    def startMove(self) -> None:
        pass

    @Slot()
    def minimize(self) -> None:
        pass

    @Slot()
    def toggleMaximize(self) -> None:
        pass


@pytest.fixture(scope="module")
def isolated_home(tmp_path_factory):
    """把「用户目录」重定向到临时目录，避免读写真实的 config.toml。"""
    home = tmp_path_factory.mktemp("home")
    import os

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
def window(qt_app, isolated_home):
    """实例化一次 PreviewWindow，供整个模块复用（构建成本较高）。

    qt_app 由 conftest 的 session fixture 提供（QGuiApplication）。
    """
    model = PreviewModel()
    model.begin("修一下订单接口")
    ctl = _WindowCtlStub()
    settings = SettingsModel()
    shortcut_ctl = ShortcutController(settings)

    view = QQuickView()
    configure(view)
    view.rootContext().setContextProperty("preview", model)
    view.rootContext().setContextProperty("windowCtl", ctl)
    view.rootContext().setContextProperty("shortcut_ctl", shortcut_ctl)
    view.setSource(source("PreviewWindow.qml"))
    check(view, "PreviewWindow")  # 有 QML 错误直接失败
    view.show()
    qt_app.processEvents()
    return model, ctl, view.rootObject(), view, shortcut_ctl


def _shortcut_items(root) -> list:
    """收集 QML 里所有 Shortcut 项（Shortcut 是 QObject，不是 Item）。"""
    found: list = []

    def walk(obj: QObject) -> None:
        for child in obj.children():
            if "Shortcut" in str(child.metaObject().className()):
                found.append(child)
            walk(child)

    walk(root)
    return found


def _all_sequences(root) -> list[str]:
    """所有已注册的键序列（含 sequences 复数形式里的每一条）。"""
    sequences: list[str] = []
    for item in _shortcut_items(root):
        many = item.property("sequences")
        if many:
            sequences.extend(str(s) for s in many)
        else:
            single = item.property("sequence")
            if single:
                sequences.append(str(single))
    return sequences


def _text_area_with_edit(root):
    """返回 (AppTextArea, 内部 TextEdit)。"""
    area = None
    stack = list(root.childItems())
    while stack:
        item = stack.pop()
        try:
            if item.property("markdown") is not None and item.property("editing") is not None:
                area = item
                break
        except (RuntimeError, TypeError):
            pass
        stack.extend(item.childItems())

    def find_edit(obj):
        for child in obj.childItems():
            if "TextEdit" in str(child.metaObject().className()):
                return child
            deeper = find_edit(child)
            if deeper is not None:
                return deeper
        return None

    return area, find_edit(area) if area else None


# ---------- 硬约束：不许有单字母键 ----------
def test_no_bare_letter_shortcut_anywhere(window):
    """窗口里注册的每一个键序列都必须是组合键（或 Esc 这类非打印键）。

    这条断言是整套快捷键设置功能的成败线：单字母键会和打字抢输入。
    """
    sequences = _all_sequences(window[2])
    assert sequences, "一个 Shortcut 都没注册，绑定接线断了"

    # Esc 这类非打印键不算违规：它打不出字符，抢不了输入
    bare = [s for s in sequences if conflicts_with_typing(s)]
    assert bare == [], f"出现了会与打字冲突的单键快捷键：{bare}"


def test_every_action_has_a_registered_shortcut(window):
    """七个动作一个都不能少绑——少一个就是有人加了动作忘了接线。"""
    _, _, root, _, shortcut_ctl = window
    sequences = set(_all_sequences(root))
    bindings = shortcut_ctl.bindings

    for action in ACTION_IDS:
        variants_ = shortcut_ctl.sequences.get(action) or []
        assert variants_, f"{action} 没有可注册的键序列"
        assert any(v.lower() in {s.lower() for s in sequences} for v in variants_)
    assert set(bindings) == set(ACTION_IDS)


def test_typing_does_not_steal_letters(window, qt_app):
    """在输入框里打字，不会触发任何窗口快捷键。

    这是「禁单字母键」的直接收益：从前靠 enabled 门控，换个键就复发；
    现在规则上不允许裸键，焦点在不在输入框都无所谓。
    """
    _, _, root, _, _ = window
    area, edit = _text_area_with_edit(root)
    assert edit is not None

    edit.forceActiveFocus()
    qt_app.processEvents()
    assert area.property("editing") is True

    for sequence in _all_sequences(root):
        assert not conflicts_with_typing(sequence), sequence

    edit.setProperty("focus", False)
    qt_app.processEvents()


def test_switching_scheme_rebinds_live(window, qt_app):
    """设置页切方案：主窗口的键位必须立刻跟着变，不需要重启。"""
    _, _, root, _, shortcut_ctl = window
    before = set(_all_sequences(root))

    shortcut_ctl.setScheme("ctrl")
    qt_app.processEvents()

    after = set(_all_sequences(root))
    assert after != before
    # 纯 Ctrl 系的视图键应已出现在注册列表里
    lowered = {s.lower().replace(" ", "") for s in after}
    assert "ctrl+e" in lowered

    shortcut_ctl.setScheme("balanced")
    qt_app.processEvents()


def test_escape_closes_window(window):
    """Esc 在主页面触发关窗（走 windowCtl，按配置决定退托盘还是退出）。"""
    _, ctl, root, _, _ = window
    ctl.closed = False

    # 直接调用而非模拟按键：offscreen 下快捷键分发不可靠，
    # 这里验证的是「Esc 这条 Shortcut 接到的是关窗」这层接线。
    for item in _shortcut_items(root):
        if str(item.property("sequence")).lower() == "esc":
            item.activated.emit()
            break

    assert ctl.closed is True


def test_use_shortcut_sends_edited_result(window, qt_app):
    """「使用增强结果」带走的是结果框当前文本。"""
    model, _, root, _, _ = window
    sent = []
    model.useRequested.connect(sent.append)

    model.set_result(
        EnhancedPrompt(
            original_prompt="修一下订单接口",
            enhanced_prompt="## 目标\n修复订单接口",
            budget_tokens=6000,
        )
    )
    qt_app.processEvents()

    root.triggerUse()
    assert len(sent) == 1
    assert sent[0] == "## 目标\n修复订单接口"


def test_enhance_shortcut_not_fired_while_busy(window, qt_app):
    """增强进行中时，快捷键不得重复发起（与按钮的防重复点击一致）。"""
    model, _, root, _, _ = window
    requested = []
    model.enhanceRequested.connect(requested.append)

    requested.clear()
    model.enhance("第一次")
    count_after_first = len(requested)
    root.triggerEnhance()  # 增强中再次触发，应被忽略

    assert len(requested) == count_after_first
