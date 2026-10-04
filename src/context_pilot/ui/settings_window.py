"""设置窗口：常驻 QQuickView，可反复 show/hide。"""

from PySide6.QtGui import QColor
from PySide6.QtQuick import QQuickView

from context_pilot.ui import qml_setup
from context_pilot.ui.settings_model import SettingsModel


class SettingsWindow:
    def __init__(self, model: SettingsModel) -> None:
        self._view = QQuickView()
        self._view.setTitle("ContextPilot 设置")
        self._view.setColor(QColor("#0E0F12"))
        self._view.setResizeMode(QQuickView.ResizeMode.SizeViewToRootObject)

        qml_setup.configure(self._view)
        self._view.rootContext().setContextProperty("settings", model)
        self._view.setSource(qml_setup.source("SettingsWindow.qml"))
        qml_setup.check(self._view, "设置界面")

    def show_and_activate(self) -> None:
        self._view.show()
        self._view.raise_()
        self._view.requestActivate()

    def hide(self) -> None:
        self._view.hide()
