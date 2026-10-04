"""预览窗口：常驻的 QQuickView，可被热键反复 show/hide。

用 QQuickView 而非 QQmlApplicationEngine + Window 根对象：后者关闭即销毁，
无法复用；QQuickView 是常驻 QWindow，反复 show()/hide() 安全。
"""

import ctypes
from collections.abc import Callable

from PySide6.QtGui import QColor
from PySide6.QtQuick import QQuickView

from context_pilot.ui import qml_setup
from context_pilot.ui.preview_model import PreviewModel


class PreviewWindow:
    def __init__(
        self, model: PreviewModel, on_close: Callable[[], None] | None = None
    ) -> None:
        self._on_close = on_close
        self._view = QQuickView()
        self._view.setTitle("ContextPilot")
        self._view.setColor(QColor("#0E0F12"))
        self._view.setResizeMode(QQuickView.ResizeMode.SizeViewToRootObject)

        # 注入顺序：先配置引擎与上下文属性，再 setSource
        qml_setup.configure(self._view)
        self._view.rootContext().setContextProperty("preview", model)
        self._view.setSource(qml_setup.source("PreviewWindow.qml"))
        qml_setup.check(self._view, "预览窗")

        self._view.closing.connect(self._on_closing)

    def _on_closing(self, event) -> None:
        """拦截原生关闭按钮：由回调决定隐藏还是退出。"""
        event.accept()
        if self._on_close is not None:
            self._on_close()
        else:
            self._view.hide()

    def set_close_behavior(self, on_close: Callable[[], None]) -> None:
        self._on_close = on_close

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
