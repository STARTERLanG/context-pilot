"""应用图标：统一从 resources/icon.ico 加载，托盘 / 窗口 / 任务栏共用。

图标由 scripts/generate_icon.py 生成（teal 主题，多尺寸 16~256px），
若资源文件缺失则返回空 QIcon，由调用方决定兜底方案。
"""

from pathlib import Path

from PySide6.QtGui import QIcon

_ICON_CACHE: QIcon | None = None


def icon_path() -> Path:
    return Path(__file__).parent / "resources" / "icon.ico"


def app_icon() -> QIcon:
    """返回应用图标（进程内缓存，多次调用不重复解码）。"""
    global _ICON_CACHE
    if _ICON_CACHE is None:
        path = icon_path()
        _ICON_CACHE = QIcon(str(path)) if path.exists() else QIcon()
    return _ICON_CACHE
