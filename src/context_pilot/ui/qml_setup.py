"""QML 引擎装配：注册组件目录并注入主题。

QQuickView 内部使用 QQmlEngine，通过 view.engine() 拿到后配置，保证
预览窗与设置窗共用同一套组件与主题。
"""

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtQuick import QQuickView

from context_pilot.ui.theme import THEME

QML_DIR = Path(__file__).parent / "qml"


def configure(view: QQuickView) -> None:
    """给视图的 QML 引擎加上组件导入路径与主题属性。"""
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
