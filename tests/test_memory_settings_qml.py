"""设置页「记忆管理」QML 集成验证：真实加载页面，确认绑定与渲染。"""

from PySide6.QtQuick import QQuickView

from context_pilot.memory.models import MemoryType
from context_pilot.memory.store import MemoryStore

from context_pilot.ui import qml_setup
from context_pilot.ui.memory_manage_controller import MemoryManageController


def test_settings_memory_page_loads(qt_app, tmp_path):
    ctl = MemoryManageController(str(tmp_path), base_dir=tmp_path / "memroot")
    view = QQuickView()
    qml_setup.configure(view)
    view.rootContext().setContextProperty("memoryManageCtl", ctl)
    view.setSource(qml_setup.source("settings/SettingsMemory.qml"))
    qml_setup.check(view, "SettingsMemory")
    root = view.rootObject()
    assert root is not None
    qt_app.processEvents()


def test_memory_cards_have_height_and_do_not_overlap(qt_app, tmp_path):
    """回归：卡片必须有正高度且纵向不重叠（旧布局高度塌陷会全叠在一起）。"""
    memroot = tmp_path / "memroot"
    store = MemoryStore(tmp_path, base_dir=memroot)
    store.add("第一条较长的记忆内容用于撑开卡片高度", MemoryType.PROJECT_FACT)
    store.add("第二条记忆内容", MemoryType.USER_PREFERENCE)
    ctl = MemoryManageController(str(tmp_path), base_dir=memroot)

    view = QQuickView()
    qml_setup.configure(view)
    view.rootContext().setContextProperty("memoryManageCtl", ctl)
    view.setSource(qml_setup.source("settings/SettingsMemory.qml"))
    qml_setup.check(view, "SettingsMemory")
    view.resize(720, 560)
    view.show()
    qt_app.processEvents()

    root = view.rootObject()
    root.setProperty("width", 720)
    root.setProperty("height", 560)
    qt_app.processEvents()

    cards = root.cardGeometry()
    cards = cards.toVariant() if hasattr(cards, "toVariant") else cards
    assert len(cards) == 2
    for card in cards:
        assert card["height"] > 20, f"卡片高度塌陷：{card}"
    ordered = sorted(cards, key=lambda c: c["y"])
    assert ordered[0]["y"] + ordered[0]["height"] <= ordered[1]["y"] + 1
    # 工具栏必须保持单行高度：曾因子项 Layout.fillHeight 膨胀到整页
    assert 28 <= root.toolbarHeight() <= 44, root.toolbarHeight()


def test_editor_popup_height_fits_content(qt_app, tmp_path):
    """弹窗高度随内容走，控件不因宽度为 0 而消失。"""
    ctl = MemoryManageController(str(tmp_path), base_dir=tmp_path / "memroot")
    view = QQuickView()
    qml_setup.configure(view)
    view.rootContext().setContextProperty("memoryManageCtl", ctl)
    view.setSource(qml_setup.source("settings/SettingsMemory.qml"))
    qml_setup.check(view, "SettingsMemory")
    view.resize(720, 560)
    view.show()
    qt_app.processEvents()

    root = view.rootObject()
    root.setProperty("width", 720)
    root.setProperty("height", 560)
    qt_app.processEvents()
    root.openEditorForTest()
    qt_app.processEvents()

    height = root.editorHeight()
    assert 150 <= height <= 320, height


def test_settings_page_has_memory_tab(qt_app, tmp_path):
    """SettingsPage 真实加载后应含第 7 个标签「记忆管理」。"""
    from context_pilot.ui.preview_model import PreviewModel
    from context_pilot.ui.session_controller import SessionController
    from context_pilot.ui.settings_controller import SettingsController
    from context_pilot.ui.settings_model import SettingsModel
    from context_pilot.ui.shortcut_controller import ShortcutController

    settings = SettingsModel()
    view = QQuickView()
    qml_setup.configure(view)
    view.rootContext().setContextProperty("preview", PreviewModel())
    view.rootContext().setContextProperty("settings", settings)
    view.rootContext().setContextProperty("settingsCtl", SettingsController(settings))
    view.rootContext().setContextProperty("sessionCtl", SessionController(settings.config))
    view.rootContext().setContextProperty("shortcut_ctl", ShortcutController(settings))
    view.rootContext().setContextProperty(
        "memoryManageCtl", MemoryManageController(base_dir=tmp_path / "memroot")
    )
    # SettingsPage 由 PreviewWindow 的 Loader 加载；这里直接加载验证 tabs 数组
    view.setSource(qml_setup.source("settings/SettingsPage.qml"))
    qml_setup.check(view, "SettingsPage")
    root = view.rootObject()
    assert root is not None
    qt_app.processEvents()
    tabs = root.property("tabs")
    tabs = tabs.toVariant() if hasattr(tabs, "toVariant") else tabs
    assert "记忆管理" in tabs
