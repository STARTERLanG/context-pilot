"""ContextPilot 快捷键功能的唯一实现主体。

把所有与快捷键相关的逻辑——按键解析、设置/配置、映射、冲突处理、全局热键的
跨平台注册与触发分发——集中到本包，对外只暴露清晰的公共接口，其他模块通过
这里 import，不感知内部实现细节。

分层：
    keys.py        解析 / 校验 / 格式化（纯逻辑，无 Qt）
    qt_keys.py     Qt 键码 → 字符串映射（唯一依赖 Qt 的换算层）
    registry.py    动作清单 / 方案 / 校验 / 归一化 / 冲突检测（纯逻辑）
    manager.py     统一注册 / 查询 / 改绑 / 触发分发的编排入口
    global_hotkey.py  全局热键门面（平台分发 + GlobalHotkey）
    backends/      各平台全局热键后端（windows / macos / x11 / wayland）
    errors.py      异常类型

历史 import 路径（platform.keys / platform.hotkey* / core.shortcuts）仍保留为
兼容转发，指向本包，保证存量调用与测试零改动。
"""

from context_pilot.shortcuts.errors import (
    HotkeyParseError,
    HotkeyRegistrationError,
    UnsupportedPlatformError,
)
from context_pilot.shortcuts.global_hotkey import GlobalHotkey
from context_pilot.shortcuts.manager import ShortcutManager
from context_pilot.shortcuts import keys, qt_keys, registry

__all__ = [
    "GlobalHotkey",
    "ShortcutManager",
    "HotkeyParseError",
    "HotkeyRegistrationError",
    "UnsupportedPlatformError",
    "keys",
    "qt_keys",
    "registry",
]
