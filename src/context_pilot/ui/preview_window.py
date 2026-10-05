"""预览窗口：常驻的 QQuickView，可被热键反复 show/hide。

用 QQuickView 而非 QQmlApplicationEngine + Window 根对象：后者关闭即销毁，
无法复用；QQuickView 是常驻 QWindow，反复 show()/hide() 安全。
"""

import ctypes
from collections.abc import Callable

from PySide6.QtCore import Property, QObject, Qt, Signal, Slot
from PySide6.QtGui import QCloseEvent, QColor, QWindow
from PySide6.QtQuick import QQuickView

from context_pilot.ui import qml_setup
from context_pilot.ui.icon import app_icon
from context_pilot.ui.preview_model import PreviewModel


class _CloseableQuickView(QQuickView):
    """可拦截关闭事件的 QQuickView。

    QQuickView 的 closing 信号携带 QQuickCloseEvent（QtQuick 内部类型，
    PySide6 不导出为可实例化的 Python 类型），直接连接槽会触发
    "Cannot call meta function slot(QQuickCloseEvent*)" 类型转换错误。

    改用重写 closeEvent（标准 QCloseEvent，可正常转换）：拦截原生关闭
    按钮，交由回调决定隐藏到托盘还是退出，窗口保持常驻可复用。
    """

    def __init__(self, on_close: Callable[[], None] | None = None) -> None:
        super().__init__()
        self._on_close = on_close

    def set_close_behavior(self, on_close: Callable[[], None] | None) -> None:
        self._on_close = on_close

    def closeEvent(self, event: QCloseEvent) -> None:
        """拦截关闭：阻止默认销毁，改由回调决定隐藏或退出。"""
        event.ignore()  # 阻止窗口被销毁，保持常驻
        if self._on_close is not None:
            self._on_close()
        else:
            self.hide()


class _WindowCtl(QObject):
    """QML → Python 桥：无边框窗口的原生拖动与标准窗口控制。

    主窗口为 FramelessWindowHint（无标题栏），QML 顶栏 MouseArea 调用
    startMove() 进入系统级移动循环，比手动改 x/y 平滑且不丢捕获。
    最小化/最大化/关闭则由顶栏自绘按钮经此处调用原生 API。

    isMaximized 供 QML 绑定：最大化时去掉圆角/阴影边距，无缝铺满屏幕。
    """

    maximizedChanged = Signal()

    def __init__(self, view: QQuickView, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._view = view
        # 可见性变化（含最小化/最大化/还原）时通知 QML 重读 isMaximized
        self._view.visibilityChanged.connect(self._on_visibility)

    def _on_visibility(self, _visibility) -> None:
        self.maximizedChanged.emit()

    @Property(bool, notify=maximizedChanged)
    def isMaximized(self) -> bool:
        # QWindow（区别于 QWidget）没有 isMaximized()，用 visibility 判断
        return self._view.visibility() == QWindow.Visibility.Maximized

    @Slot()
    def startMove(self) -> None:
        self._view.startSystemMove()

    @Slot()
    def minimize(self) -> None:
        self._view.showMinimized()

    @Slot()
    def toggleMaximize(self) -> None:
        if self._view.visibility() == QWindow.Visibility.Maximized:
            self._view.showNormal()
        else:
            self._view.showMaximized()

    @Slot()
    def close(self) -> None:
        # 复用 closeEvent 拦截逻辑（隐藏到托盘或退出）
        self._view.close()


class PreviewWindow:
    def __init__(
        self, model: PreviewModel, on_close: Callable[[], None] | None = None
    ) -> None:
        self._on_close = on_close
        self._view = _CloseableQuickView(on_close)
        # 任务栏 / Alt-Tab 仍需名称与图标；标题栏本身已随 Frameless 移除
        self._view.setTitle("ContextPilot")
        self._view.setIcon(app_icon())
        self._view.setFlags(self._view.flags() | Qt.WindowType.FramelessWindowHint)
        # 透明背景：圆角与阴影由 QML 根 Rectangle 自绘，窗口底色必须透明
        # 才能露出阴影与圆角（否则黑色/灰色填充角落）。
        self._view.setColor(QColor(0, 0, 0, 0))
        # SizeRootObjectToView：root 跟随 view 尺寸变化，最大化/还原时
        # QML 内容能随窗口铺满（SizeViewToRootObject 会因 root 固定尺寸
        # 把 showMaximized 拉回原大小，导致放大按钮失效）。
        self._view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
        self._view.resize(752, 712)

        # 注入顺序：先配置引擎与上下文属性，再 setSource
        qml_setup.configure(self._view)
        self._ctl = _WindowCtl(self._view)
        self._view.rootContext().setContextProperty("windowCtl", self._ctl)
        self._view.rootContext().setContextProperty("preview", model)
        self._view.setSource(qml_setup.source("PreviewWindow.qml"))
        qml_setup.check(self._view, "预览窗")

    def set_close_behavior(self, on_close: Callable[[], None]) -> None:
        self._on_close = on_close
        self._view.set_close_behavior(on_close)

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
