"""记忆确认弹窗的 QML 集成验证：真实加载 PreviewWindow.qml。

确认三件事：新注入的 memoryCtl 在 QML 里可用、弹窗对象存在、候选数能驱动
按钮角标。不验证复杂交互（QML 点击链路由 controller 单测覆盖），只锁住
「Python 属性 ↔ QML 绑定」这条最容易在重构中断掉的线。
"""

from PySide6.QtQuick import QQuickView

from context_pilot.ui import qml_setup
from context_pilot.ui.memory_controller import MemoryController
from context_pilot.ui.preview_model import PreviewModel
from context_pilot.ui.session_controller import SessionController
from context_pilot.ui.settings_model import SettingsModel
from context_pilot.ui.shortcut_controller import ShortcutController


class _WindowCtlStub:
    isMaximized = False

    def close(self) -> None:
        pass

    def minimize(self) -> None:
        pass

    def toggleMaximize(self) -> None:
        pass


def test_memory_popup_loads_and_binds(qt_app, tmp_path):
    model = PreviewModel()
    settings = SettingsModel()
    memory = MemoryController(str(tmp_path), base_dir=tmp_path / "memroot")
    view = QQuickView()
    qml_setup.configure(view)
    view.rootContext().setContextProperty("preview", model)
    view.rootContext().setContextProperty("windowCtl", _WindowCtlStub())
    view.rootContext().setContextProperty("settings", settings)
    view.rootContext().setContextProperty("sessionCtl", SessionController(settings.config))
    view.rootContext().setContextProperty("shortcut_ctl", ShortcutController(settings))
    view.rootContext().setContextProperty("memoryCtl", memory)
    view.setSource(qml_setup.source("PreviewWindow.qml"))
    qml_setup.check(view, "PreviewWindow")
    root = view.rootObject()
    assert root is not None
    qt_app.processEvents()

    def find(object_name):
        found = []

        def walk(obj):
            if obj.objectName() == object_name:
                found.append(obj)
            for child in obj.children():
                walk(child)

        walk(root)
        return found

    assert len(find("memoryPopup")) == 1


def test_memory_candidates_drive_badge(qt_app, tmp_path):
    model = PreviewModel()
    settings = SettingsModel()
    memory = MemoryController(str(tmp_path), base_dir=tmp_path / "memroot")
    view = QQuickView()
    qml_setup.configure(view)
    for name, obj in (
        ("preview", model),
        ("windowCtl", _WindowCtlStub()),
        ("settings", settings),
        ("sessionCtl", SessionController(settings.config)),
        ("shortcut_ctl", ShortcutController(settings)),
        ("memoryCtl", memory),
    ):
        view.rootContext().setContextProperty(name, obj)
    view.setSource(qml_setup.source("PreviewWindow.qml"))
    qml_setup.check(view, "PreviewWindow")
    qt_app.processEvents()

    assert memory.collect("必须使用 FastAPI。不要直连数据库。") == 2
    qt_app.processEvents()
    assert len(memory.candidates) == 2
