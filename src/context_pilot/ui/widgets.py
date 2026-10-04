"""设置界面自定义控件：Toggle 开关、圆角下拉框、热键捕获框。

全部用 Qt Widgets 基础类 + 手绘，避免依赖图片资源。颜色与 QSS 一致。
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QStyle,
    QStyleOptionComboBox,
    QStylePainter,
)


class Card(QFrame):
    """分组卡片：白底、圆角 12、细边、内边距 20（objectName=Card 由 QSS 生效）。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")


class ToggleSwitch(QAbstractButton):
    """iOS 风格开关：手绘轨道与滑块，开启态青绿色 #14B8A6。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(44, 24)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width, height = self.width(), self.height()

        on = self.isChecked()
        track_color = QColor("#3B82F6") if on else QColor("#E5E7EB")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(0, 0, width, height, height // 2, height // 2)

        knob = QColor("#FFFFFF")
        padding = 2
        diameter = height - padding * 2
        x = width - diameter - padding if on else padding
        painter.setBrush(knob)
        painter.setPen(QPen(QColor("#D1D5DB"), 1))
        painter.drawEllipse(x, padding, diameter, diameter)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        super().mouseReleaseEvent(event)
        self.update()


class ArrowComboBox(QComboBox):
    """圆角下拉框：去掉原生箭头，右侧自绘小三角。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event) -> None:
        # 先画原生下拉框（含 QSS 圆角边框），再补画自绘箭头
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        painter = QStylePainter(self)
        painter.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, option)

        rect = self.rect()
        arrow_x = rect.right() - 18
        arrow_y = rect.center().y()
        pen = QPen(QColor("#6B7280"), 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(arrow_x - 4, arrow_y - 2, arrow_x, arrow_y + 2)
        painter.drawLine(arrow_x, arrow_y + 2, arrow_x + 4, arrow_y - 2)


class HotkeyEdit(QLineEdit):
    """热键捕获框：点击获得焦点后捕获下一次组合键。"""

    captured = Signal(str)

    def __init__(self, value: str = "", parent=None) -> None:
        super().__init__(parent)
        self._capturing = False
        self._value = value
        self.setFixedHeight(36)
        self.setReadOnly(True)
        self.setPlaceholderText("点击后按下组合键")
        self.refresh_text()

    def refresh_text(self) -> None:
        self.setText("请按下组合键…" if self._capturing else self._value)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._capturing = True
        self.refresh_text()
        self.setFocus()
        event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if not self._capturing:
            super().keyPressEvent(event)
            return
        if event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            self._capturing = False
            self.refresh_text()
            event.accept()
            return

        modifiers = event.modifiers()
        key = event.key()
        from context_pilot.ui.settings_model import SettingsModel

        sequence = SettingsModel.format_key(modifiers, key)
        if sequence:
            self._value = sequence
            self._capturing = False
            self.refresh_text()
            self.captured.emit(sequence)
        event.accept()
