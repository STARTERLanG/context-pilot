"""开机自启：写 HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run。

只动当前用户的注册表项，不需要管理员权限。非 Windows 平台为无操作。
"""

import sys
from pathlib import Path

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_APP_NAME = "ContextPilot"


def _command() -> str:
    """自启命令：优先用打包后的 exe，否则用 pythonw + 模块入口。"""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    # pythonw.exe 无控制台窗口，适合托盘常驻
    python = Path(sys.executable)
    pythonw = python.with_name("pythonw.exe")
    interpreter = pythonw if pythonw.exists() else python
    return f'"{interpreter}" -m context_pilot'


def is_enabled() -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, _APP_NAME)
    except FileNotFoundError:
        return False
    return True


def enable() -> None:
    if sys.platform != "win32":
        return
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
        winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, _command())


def disable() -> None:
    if sys.platform != "win32":
        return
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, _APP_NAME)
    except FileNotFoundError:
        return


def apply(enabled: bool) -> None:
    (enable if enabled else disable)()
