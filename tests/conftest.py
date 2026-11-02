"""pytest 全局配置：统一在最前面建立 Qt 应用实例。

背景：QML 测试需要 QGuiApplication（QQuickView 在 QCoreApplication 下会直接
段错误退出），而较早的测试模块各自用 `QCoreApplication.instance() or
QCoreApplication([])` 建过 QCoreApplication。PySide **不支持**把已有实例
升级成 QGuiApplication，谁后谁崩——表现为 pytest 进程在某个测试后无声消失、
退出码 127，而不是明确的断言失败。

所以这里用一个 session 级 autouse fixture 保证：任何模块 fixture 运行前，
进程里已经存在且仅存在 QGuiApplication。其余测试拿到的 instance() 依然满足
QCoreApplication 的用法（继承关系向下兼容）。

offscreen 平台必须在 QGuiApplication 构造之前写到环境变量，因此放在模块
导入期而非 fixture 内。
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    """会话唯一的 Qt 应用实例。返回类型是 QGuiApplication。"""
    existing = QGuiApplication.instance()
    if existing is not None and not isinstance(existing, QGuiApplication):
        raise RuntimeError(
            "进程里已有非 QGuiApplication 的 Qt 实例，无法升级。"
            "请检查是否有模块在本 fixture 之前创建了 QCoreApplication。"
        )
    app = existing if existing is not None else QGuiApplication([])
    return app
