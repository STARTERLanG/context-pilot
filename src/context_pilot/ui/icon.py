"""应用图标：统一从 resources/icon.ico 加载，托盘 / 窗口 / 任务栏共用。

图标由 scripts/generate_icon.py 生成（teal 主题，多尺寸 16~256px），
若资源文件缺失则返回空 QIcon，由调用方决定兜底方案。

路径解析必须同时满足两种运行形态：
  * 源码运行（含 editable 安装）：图标就在本包目录下的 resources/；
  * wheel 安装：resources/ 作为包数据随 context_pilot.ui 一起分发。
用 importlib.resources 取路径，它在两种形态下都成立；只有极端部署
（zipapp / zipimport，资源不在真实文件系统里）才回退空 QIcon。
"""

from importlib.resources import as_file, files
from pathlib import Path

from PySide6.QtGui import QIcon

_ICON_CACHE: QIcon | None = None

_PACKAGE = "context_pilot.ui"
_RESOURCE_PARTS = ("resources", "icon.ico")


def icon_path() -> Path:
    """返回图标文件路径；资源不可解析时返回空路径（不代表文件存在）。"""
    try:
        resource = files(_PACKAGE).joinpath(*_RESOURCE_PARTS)
        # 常规文件系统安装：as_file 直接返回原路径，不会复制文件
        with as_file(resource) as resolved:
            return Path(resolved)
    except (ModuleNotFoundError, FileNotFoundError, TypeError, OSError):
        # 资源系统无法定位（如 zip 部署）：宁可返回空图标，也不要让启动崩掉
        return Path()


def app_icon() -> QIcon:
    """返回应用图标（进程内缓存，多次调用不重复解码）。

    资源缺失时返回空 QIcon 而非抛异常——图标缺失不该阻断启动，
    tray.py 里有程序化绘制的兜底图标。
    """
    global _ICON_CACHE
    if _ICON_CACHE is None:
        path = icon_path()
        _ICON_CACHE = QIcon(str(path)) if path and path.exists() else QIcon()
    return _ICON_CACHE
