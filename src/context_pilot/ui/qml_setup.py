"""QML 引擎装配：注册组件目录并注入主题。

QQuickView 内部使用 QQmlEngine，通过 view.engine() 拿到后配置，保证
预览窗与设置窗共用同一套组件与主题。
"""

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtQuick import QQuickView
from PySide6.QtQuickControls2 import QQuickStyle

from context_pilot.ui.theme import THEME

QML_DIR = Path(__file__).parent / "qml"


def configure(view: QQuickView) -> None:
    """给视图的 QML 引擎加上组件导入路径与主题属性。"""
    # 强制使用 Fusion（非原生）样式：Windows 原生样式不允许自定义控件
    # 的 contentItem（如 ScrollBar），会触发 "does not support customization"
    # 告警。Fusion 跨平台一致，且本项目 UI 全部基于自绘 + theme 令牌，
    # 不依赖原生外观，切样式不会改变视觉。必须在加载任何 QML 之前设置。
    QQuickStyle.setStyle("Fusion")

    engine = view.engine()
    engine.addImportPath(str(QML_DIR))
    view.rootContext().setContextProperty("theme", THEME)


def source(name: str) -> QUrl:
    return QUrl.fromLocalFile(str(QML_DIR / name))


def check(view: QQuickView, label: str) -> None:
    """QML 加载失败是静默空白，必须显式检查。"""
    if view.status() == QQuickView.Status.Error:
        details = "\n".join(str(e) for e in view.errors())
        raise RuntimeError(f"{label} QML 加载失败：\n{details}")
