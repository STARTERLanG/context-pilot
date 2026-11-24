"""应用图标：统一从 resources/ 加载，窗口 / 任务栏 / 托盘共用同一套 Signal 图形。

图标由 scripts/generate_icon.py 生成，共有四个变体（详见 docs/icon-design.md）：
    app_icon()          主图标：白底 + 深墨递进 + teal 末段（窗口 / 任务栏）
    app_icon_dark()     深色反白版：深墨底 + 近白 + 亮 teal（深色主题备用）
    tray_icon(light)    托盘单色版：透明底，按系统任务栏明暗选择浅 / 深两版

路径解析必须同时满足两种运行形态：
  * 源码运行（含 editable 安装）：图标就在本包目录下的 resources/；
  * wheel 安装：resources/ 作为包数据随 context_pilot.ui 一起分发。
用 importlib.resources 取路径，它在两种形态下都成立；只有极端部署
（zipapp / zipimport，资源不在真实文件系统里）才回退空 QIcon。

资源缺失时一律返回空 QIcon 而不抛异常——图标不该阻断启动，
tray.py / preview_window.py 里有程序化绘制的兜底。
"""

from __future__ import annotations

from importlib.resources import as_file, files
from pathlib import Path

from PySide6.QtGui import QIcon

_RESOURCE_PARTS = ("resources",)
_PACKAGE = "context_pilot.ui"

# 变体 → 文件名
_FILES = {
    "app": "icon.ico",
    "app_dark": "icon_dark.ico",
    "tray_light": "tray_light.ico",
    "tray_dark": "tray_dark.ico",
}

_CACHE: dict[str, QIcon] = {}
_MISSING: set[str] = set()


def resource_path(filename: str) -> Path:
    """返回图标资源路径；资源系统无法定位时返回空路径。"""
    try:
        resource = files(_PACKAGE).joinpath(*_RESOURCE_PARTS, filename)
        # 常规文件系统安装：as_file 直接返回原路径，不会复制文件
        with as_file(resource) as resolved:
            return Path(resolved)
    except (ModuleNotFoundError, FileNotFoundError, TypeError, OSError):
        return Path()


def _icon(variant: str) -> QIcon:
    if variant in _CACHE:
        return _CACHE[variant]
    if variant in _MISSING:
        return QIcon()

    path = resource_path(_FILES[variant])
    if path and path.exists():
        icon = QIcon(str(path))
        if not icon.isNull():
            _CACHE[variant] = icon
            return icon

    # 缺失结果也缓存，避免托盘重绘 / 主题切换时反复探测磁盘
    _MISSING.add(variant)
    return QIcon()


def app_icon() -> QIcon:
    """主图标：窗口、任务栏、快捷方式使用。"""
    return _icon("app")


def app_icon_dark() -> QIcon:
    """深色反白主图标，供深色主题窗口 / 对话框备用。"""
    return _icon("app_dark")


def tray_icon(light: bool = True) -> QIcon:
    """托盘单色图标：light=True 用深墨图形（浅色任务栏），False 用近白图形。"""
    return _icon("tray_light" if light else "tray_dark")
