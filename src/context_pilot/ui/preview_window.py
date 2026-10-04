"""预览窗口：常驻的 QQuickView，可被热键反复 show/hide。

用 QQuickView 而非 QQmlApplicationEngine + Window 根对象：后者关闭即销毁，
无法复用；QQuickView 是常驻 QWindow，反复 show()/hide() 安全。
"""

import ctypes
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QColor
from PySide6.QtQuick import QQuickView

from context_pilot.ui.preview_model import PreviewModel

_QML_PATH = Path(__file__).parent / "qml" / "PreviewWindow.qml"


class PreviewWindow:
    def __init__(self, model: PreviewModel) -> None:
        self._view = QQuickView()
        self._view.setTitle("ContextPilot")
        self._view.setColor(QColor("#17181b"))
        self._view.setResizeMode(QQuickView.ResizeMode.SizeViewToRootObject)

        # 必须在 setSource 之前注入，否则 QML 里取不到
        self._view.rootContext().setContextProperty("preview", model)
        self._view.setSource(QUrl.fromLocalFile(str(_QML_PATH)))

        if self._view.status() == QQuickView.Status.Error:
            details = "\n".join(str(e) for e in self._view.errors())
            raise RuntimeError(f"QML 加载失败：\n{details}")

    def show_and_activate(self) -> None:
        self._view.show()
        self._view.raise_()
        self._view.requestActivate()
        # Windows 前景锁可能拒绝 activate，用 Win32 兜底
        try:
            ctypes.windll.user32.SetForegroundWindow(int(self._view.winId()))
        except OSError:
            pass

    def hide(self) -> None:
        self._view.hide()
