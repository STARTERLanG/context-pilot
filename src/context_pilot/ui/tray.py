"""系统托盘图标与菜单。"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from context_pilot.ui.icon import app_icon


def _make_icon() -> QIcon:
    """兜底程序化图标（资源文件缺失时使用）：teal 圆角方块 + 白色 CP。"""
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#0D9488"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(4, 4, 56, 56, 14, 14)
    painter.setPen(QColor("#ffffff"))
    font = QFont()
    font.setPixelSize(28)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "CP")
    painter.end()
    return QIcon(pixmap)


def _tray_icon() -> QIcon:
    icon = app_icon()
    return icon if not icon.isNull() else _make_icon()


class Tray(QSystemTrayIcon):
    showRequested = Signal()
    settingsRequested = Signal()
    quitRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(_tray_icon(), parent)
        self.setToolTip("ContextPilot")

        menu = QMenu()
        show_action = menu.addAction("显示窗口")
        show_action.triggered.connect(self.showRequested.emit)
        settings_action = menu.addAction("设置")
        settings_action.triggered.connect(self.settingsRequested.emit)
        menu.addSeparator()
        quit_action = menu.addAction("退出")
        quit_action.triggered.connect(self.quitRequested.emit)
        # 持有菜单引用，否则被 GC 后托盘菜单消失
        self._menu = menu
        self.setContextMenu(menu)

        self.activated.connect(self._on_activated)

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.showRequested.emit()

    def notify(self, title: str, message: str) -> None:
        self.showMessage(title, message, QSystemTrayIcon.MessageIcon.Warning, 4000)
