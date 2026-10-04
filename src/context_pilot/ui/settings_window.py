"""设置窗口：常驻 QQuickView，可反复 show/hide。"""

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QColor
from PySide6.QtQuick import QQuickView

from context_pilot.ui.settings_model import SettingsModel

_QML_PATH = Path(__file__).parent / "qml" / "SettingsWindow.qml"


class SettingsWindow:
    def __init__(self, model: SettingsModel) -> None:
        self._view = QQuickView()
        self._view.setTitle("ContextPilot 设置")
        self._view.setColor(QColor("#17181b"))
        self._view.setResizeMode(QQuickView.ResizeMode.SizeViewToRootObject)

        self._view.rootContext().setContextProperty("settings", model)
        self._view.setSource(QUrl.fromLocalFile(str(_QML_PATH)))

        if self._view.status() == QQuickView.Status.Error:
            details = "\n".join(str(e) for e in self._view.errors())
            raise RuntimeError(f"设置界面 QML 加载失败：\n{details}")

    def show_and_activate(self) -> None:
        self._view.show()
        self._view.raise_()
        self._view.requestActivate()

    def hide(self) -> None:
        self._view.hide()
