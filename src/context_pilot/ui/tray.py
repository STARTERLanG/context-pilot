"""系统托盘图标与菜单。

托盘图标随 Windows 任务栏明暗自动切换：
    * 浅色任务栏 → 深墨图形（tray_light.ico）
    * 深色任务栏 → 近白图形（tray_dark.ico）
判据取注册表 SystemUsesLightTheme（这直接决定任务栏底色，比 AppsUseLightTheme
更准）；非 Windows 平台回退到 Qt 的 colorScheme。切换由两条通路触发：
    * styleHints().colorSchemeChanged —— 主题变化时立即响应；
    * 低频轮询（每 2s）—— 兜住 Qt 信号不随任务栏主题变化的情况。
"""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from context_pilot.ui.icon import tray_icon

_THEME_POLL_MS = 2000


def _system_is_light() -> bool:
    """系统任务栏是否浅色。Windows 读注册表，其余平台用 Qt colorScheme。"""
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            ) as key:
                value, _ = winreg.QueryValueEx(key, "SystemUsesLightTheme")
                return bool(value)
        except (OSError, ImportError):
            pass

    scheme = QGuiApplication.instance().styleHints().colorScheme() if QGuiApplication.instance() else None
    if scheme is not None and scheme != Qt.ColorScheme.Unknown:
        return scheme != Qt.ColorScheme.Dark
    return True  # 检测不到时按浅色处理，与浅色主界面一致


def _make_icon(light: bool = True) -> QIcon:
    """兜底程序化图标（资源文件缺失时）：Signal 简化版「圆点 + 粗斜条」。"""
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    ink = "#1A1A1A" if light else "#F2F3F4"
    accent = "#0D9488" if light else "#2DD4BF"

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(ink))
    painter.drawEllipse(20, 36, 14, 14)

    pen = painter.pen()
    pen.setColor(QColor(accent))
    pen.setWidth(9)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.drawLine(32, 32, 50, 14)
    painter.end()
    return QIcon(pixmap)


def _tray_icon(light: bool) -> QIcon:
    icon = tray_icon(light)
    return icon if not icon.isNull() else _make_icon(light)


class Tray(QSystemTrayIcon):
    showRequested = Signal()
    settingsRequested = Signal()
    quitRequested = Signal()

    def __init__(self, parent=None) -> None:
        self._light = _system_is_light()
        super().__init__(_tray_icon(self._light), parent)
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

        # 主题跟随：Qt 信号 + 轮询双保险
        app = QGuiApplication.instance()
        if app is not None:
            app.styleHints().colorSchemeChanged.connect(self._sync_theme)
        self._poll = QTimer(self)
        self._poll.setInterval(_THEME_POLL_MS)
        self._poll.timeout.connect(self._sync_theme)
        self._poll.start()

    def _sync_theme(self) -> None:
        light = _system_is_light()
        if light != self._light:
            self._light = light
            self.setIcon(_tray_icon(light))

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.showRequested.emit()

    def notify(self, title: str, message: str) -> None:
        self.showMessage(title, message, QSystemTrayIcon.MessageIcon.Warning, 4000)

