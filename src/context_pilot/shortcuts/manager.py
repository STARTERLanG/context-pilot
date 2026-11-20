"""快捷键统一管理器：对外提供注册、查询、改绑、触发分发的单一入口。

这是快捷键模块的「编排 / 门面」层。之前全局热键（GlobalHotkey）与窗口内快捷键
（registry 的绑定表）分属两套零散的调用，装配层（ui/app.py）要分别 new 对象、
分别 connect 信号、分别 rebind。本管理器把这两类收拢到一处：

- **全局热键**：增强热键 + 界面开关热键，走 GlobalHotkey 门面与平台后端。
- **窗口内快捷键**：enhance/rerun/use/close/view_* 动作的绑定表，走 registry
  的规则校验与归一化。

对调用方而言，只需拿到一个 ShortcutManager，即可：
    - register_global(name, sequence)  注册一个全局热键并拿回可连接 pressed 的对象
    - rebind_global(name, sequence)    改绑（先注销旧、再注册新）
    - query_global(name)               查当前生效序列
    - set_inwindow(action, sequence)   改某个窗口内动作的绑定（即时生效）
    - bindings() / sequences()         取窗口内绑定表 / 要注册的序列变体

本模块不直接依赖 QML；Qt 依赖（QObject / Signal）由 GlobalHotkey 内部承担。
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from context_pilot.shortcuts import registry
from context_pilot.shortcuts.global_hotkey import GlobalHotkey

__all__ = ["ShortcutManager"]


class ShortcutManager:
    """进程内所有快捷键的登记与分发。

    全局热键按 name 登记（"enhance" / "toggle" 等），窗口内快捷键按动作 id 登记，
    两类共用 registry 的冲突/校验规则，保证「同一物理键」的归一化判断一致。
    """

    def __init__(self) -> None:
        # name -> GlobalHotkey；id 从 1 起，随登记顺序递增，保证互不相同
        self._globals: dict[str, GlobalHotkey] = {}
        self._next_hotkey_id = 1
        # 窗口内绑定表：action id -> 序列字符串
        self._inwindow: dict[str, str] = {}

    # ---------- 全局热键 ----------
    def register_global(
        self,
        name: str,
        sequence: str,
        on_pressed: Callable[[], None] | None = None,
    ) -> GlobalHotkey:
        """注册（或换绑）一个全局热键并返回其 GlobalHotkey。

        同名重复调用视为换绑（先注销旧的）。on_pressed 若给出则直接 connect 到
        pressed 信号，省去调用方自己 connect 一步。返回的 GlobalHotkey 仍可继续
        connect 更多槽。

        注意：即使 register 抛 HotkeyRegistrationError（键被占用 / 平台不支持），
        该 name 也**已登记**进内部表——调用方据此仍可 get_global / rebind_global
        在稍后重试，而不是每次注册失败后对象就丢失。
        """
        existing = self._globals.get(name)
        if existing is not None:
            existing.unregister()

        hotkey = GlobalHotkey(sequence, hotkey_id=self._next_hotkey_id)
        self._next_hotkey_id += 1
        self._globals[name] = hotkey

        if on_pressed is not None:
            hotkey.pressed.connect(on_pressed)

        hotkey.register()
        return hotkey

    def rebind_global(self, name: str, sequence: str) -> GlobalHotkey:
        """改绑一个已登记的全局热键（先注销旧、再注册新）。"""
        hotkey = self._globals.get(name)
        if hotkey is None:
            raise KeyError(f"未登记的全局热键：{name}")
        hotkey.rebind(sequence)
        return hotkey

    def query_global(self, name: str) -> str | None:
        """查某个全局热键当前生效的序列；未登记返回 None。"""
        hotkey = self._globals.get(name)
        return hotkey.sequence if hotkey is not None else None

    def get_global(self, name: str) -> GlobalHotkey | None:
        """取某个已登记的全局热键对象（供连接 pressed 信号等）；未登记返回 None。"""
        return self._globals.get(name)

    def unregister_global(self, name: str) -> None:
        """注销某个全局热键。"""
        hotkey = self._globals.pop(name, None)
        if hotkey is not None:
            hotkey.unregister()

    def unregister_all_globals(self) -> None:
        for hotkey in self._globals.values():
            hotkey.unregister()
        self._globals.clear()

    # ---------- 窗口内快捷键 ----------
    def set_inwindow(self, action: str, sequence: str) -> None:
        """改某个窗口内动作的绑定（只改内存态，落盘由调用方决定）。"""
        if action not in registry.ACTION_BY_ID:
            raise ValueError(f"未知的快捷键动作：{action}")
        self._inwindow[action] = registry.canonical(sequence)

    def set_inwindow_bindings(self, bindings: Mapping[str, str]) -> None:
        """整体替换窗口内绑定表（切方案用）。"""
        self._inwindow = {
            action: registry.canonical(bindings.get(action, ""))
            for action in registry.ACTION_IDS
        }

    def inwindow_bindings(self) -> dict[str, str]:
        """取窗口内绑定表（归一化后的值）。"""
        return dict(self._inwindow)

    def inwindow_sequences(self) -> dict[str, list[str]]:
        """每个窗口内动作要注册的全部写法（Enter 连带小键盘 Return）。"""
        return {
            action: list(registry.variants(seq))
            for action, seq in self._inwindow.items()
        }

    # ---------- 校验（复用 registry 规则） ----------
    def validate_inwindow(
        self, bindings: Mapping[str, str] | None = None
    ) -> list[registry.ShortcutIssue]:
        """校验一张（或当前）窗口内绑定表。"""
        target = bindings if bindings is not None else self._inwindow
        return registry.validate_bindings(
            target,
            global_hotkeys=tuple(self._globals[name].sequence for name in self._globals),
        )
