"""轻量浮窗（Toast）：替代系统托盘气泡，用于增强结果等非阻塞提示。

设计取向：简洁、柔和、现代。

- **无遮罩层**：这是纯通知型浮窗，不打断用户当前操作，故不加模态遮罩。
- **自动淡入淡出**：出现时从右下角上浮 + 淡入，停留数秒后淡出，无需手动关闭。
- **屏幕适配**：位置按屏幕可用区（availableGeometry，含任务栏/DPI）计算，
  固定右对齐、贴底边，不同分辨率与缩放比例下都能落在视觉舒适区。
- **多条堆叠**：连续提示时逐条上移，互不遮挡。

用一个顶层 QWidget 自绘（Frameless + 半透明 + 圆角 + 阴影），比系统气泡
可控得多，也比 QML Popup 轻——它不依赖主窗口，能独立显示在屏幕任意角落。
"""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    Qt,
    QTimer,
)
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from context_pilot.ui.theme import THEME

# 外观常量
_MARGIN = 16          # 距屏幕边缘间距
_GAP = 10             # 多条浮窗之间的间距
_DURATION = 3200      # 停留时长（ms）
_FADE_IN_MS = 180     # 淡入时长
_FADE_OUT_MS = 220    # 淡出时长
_RISE_PX = 12         # 上浮距离


def _color(hex_str: str, alpha: int = 255) -> QColor:
    c = QColor(hex_str)
    c.setAlpha(alpha)
    return c


class Toast(QWidget):
    """单条浮窗。标题 + 正文 + 语义色左侧竖条 + 图标色点。

    compact 模式：更小、单行、短文案（用于「进行中」这类轻提示），
    无标题、色点更小、宽度自适应内容、停留更短。
    """

    def __init__(
        self,
        title: str,
        message: str,
        kind: str = "info",
        compact: bool = False,
        duration: int = _DURATION,
    ) -> None:
        super().__init__(None, Qt.WindowType.Tool  # 无任务栏按钮
                         | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._kind = kind
        self._compact = compact
        self._duration = duration

        if compact:
            self._build_compact(message)
        else:
            self._build_full(title, message)

        # 阴影：柔和扩散阴影，替代硬边框
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 4)
        shadow.setColor(_color("#000000", 40))
        self.setGraphicsEffect(shadow)

        if not compact:
            self.setFixedWidth(360)

    def _build_full(self, title: str, message: str) -> None:
        dot = QLabel("●")
        dot.setStyleSheet(
            f"color:{_accent_for(self._kind)}; font-size:{THEME['fontSubtitle']}px;"
        )
        dot.setFixedWidth(18)
        dot.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"color:{THEME['textPrimary']}; font-family:{THEME['fontFamily']};"
            f"font-size:{THEME['fontBody']}px; font-weight:600; background:transparent;"
        )
        msg_lbl = QLabel(message)
        msg_lbl.setWordWrap(True)
        msg_lbl.setStyleSheet(
            f"color:{THEME['textSecondary']}; font-family:{THEME['fontFamily']};"
            f"font-size:{THEME['fontSmall']}px; background:transparent;"
        )

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.addWidget(title_lbl)
        text_col.addWidget(msg_lbl)

        row = QHBoxLayout(self)
        row.setContentsMargins(16, 12, 20, 12)
        row.setSpacing(10)
        row.addWidget(dot)
        row.addLayout(text_col)

    def _build_compact(self, message: str) -> None:
        dot = QLabel("●")
        dot.setStyleSheet(
            f"color:{_accent_for(self._kind)}; font-size:{THEME['fontSmall']}px;"
        )
        dot.setFixedWidth(14)
        dot.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)

        msg_lbl = QLabel(message)
        msg_lbl.setStyleSheet(
            f"color:{THEME['textPrimary']}; font-family:{THEME['fontFamily']};"
            f"font-size:{THEME['fontSmall']}px; background:transparent;"
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 7, 14, 7)
        row.setSpacing(7)
        row.addWidget(dot)
        row.addWidget(msg_lbl)

    # ---------- 绘制 ----------
    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)
        path = QPainterPath()
        radius = THEME["radiusLg"]
        path.addRoundedRect(rect, radius, radius)

        # 背景：柔和白，带轻微半透明
        painter.fillPath(path, _color(THEME["surface"], 250))
        # 细边框
        painter.setPen(_color(THEME["border"], 200))
        painter.drawPath(path)

        # 左侧语义色竖条
        bar_w = 3 if self._compact else 4
        bar_path = QPainterPath()
        inset = 6 if self._compact else 10
        bar_path.addRoundedRect(
            rect.left(), rect.top() + inset, bar_w, rect.height() - inset * 2, 2, 2
        )
        painter.fillPath(bar_path, QColor(_accent_for(self._kind)))
        painter.end()

    # ---------- 动画 ----------
    def show_toast(self) -> None:
        """上浮 + 淡入，随后定时淡出。"""
        self.adjustSize()
        self.setWindowOpacity(0.0)
        self.show()

        # 上浮
        start = self.pos() + QPoint(0, _RISE_PX)
        self.move(start)
        rise = QPropertyAnimation(self, b"pos", self)
        rise.setDuration(_FADE_IN_MS + 60)
        rise.setStartValue(start)
        rise.setEndValue(self.pos() - QPoint(0, _RISE_PX))
        rise.setEasingCurve(QEasingCurve.Type.OutCubic)

        # 淡入
        fade_in = QPropertyAnimation(self, b"windowOpacity", self)
        fade_in.setDuration(_FADE_IN_MS)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)

        rise.start()
        fade_in.start()
        # 持有引用，防止动画对象被 GC 中途回收
        self._rise = rise
        self._fade_in = fade_in

        QTimer.singleShot(self._duration, self._fade_out)

    def _fade_out(self) -> None:
        fade = QPropertyAnimation(self, b"windowOpacity", self)
        fade.setDuration(_FADE_OUT_MS)
        fade.setStartValue(self.windowOpacity())
        fade.setEndValue(0.0)
        fade.finished.connect(self.close)
        fade.finished.connect(self.deleteLater)
        self._fade_out_anim = fade
        fade.start()


def _accent_for(kind: str) -> str:
    return {
        "success": THEME["success"],
        "warning": THEME["warning"],
        "danger": THEME["danger"],
        "info": THEME["accent"],
    }.get(kind, THEME["accent"])


class ToastManager:
    """管理多条浮窗的定位与生命周期。

    单例（模块级 _manager）。show() 时按当前已有浮窗数量向上堆叠，
    浮窗关闭后自动从登记表移除，腾出位置。
    """

    def __init__(self) -> None:
        self._active: list[Toast] = []

    def show(
        self,
        title: str,
        message: str,
        kind: str = "info",
        compact: bool = False,
        duration: int = _DURATION,
    ) -> None:
        toast = Toast(title, message, kind, compact=compact, duration=duration)
        self._active.append(toast)
        toast.destroyed.connect(lambda _=None, t=toast: self._forget(t))

        self._layout(toast)
        toast.show_toast()

    def _forget(self, toast: Toast) -> None:
        if toast in self._active:
            self._active.remove(toast)
        self._relayout()

    def _layout(self, toast: Toast) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        w = toast.width()
        h = toast.sizeHint().height()
        x = area.right() - w - _MARGIN
        y = area.bottom() - h - _MARGIN
        toast.move(x, y)

    def _relayout(self) -> None:
        """重排所有活跃浮窗，让新浮窗贴底、旧浮窗上移。"""
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        y = area.bottom() - _MARGIN
        for toast in self._active:
            h = toast.height()
            y -= h
            toast.move(area.right() - toast.width() - _MARGIN, y)
            y -= _GAP


_manager: ToastManager | None = None


def toast(
    title: str,
    message: str,
    kind: str = "info",
    compact: bool = False,
    duration: int = _DURATION,
) -> None:
    """模块级入口：弹一条浮窗提示。

    compact=True 弹出小号单行浮窗（用于「进行中」等轻提示，短文案）。
    """
    global _manager
    if _manager is None:
        _manager = ToastManager()
    _manager.show(title, message, kind, compact=compact, duration=duration)
