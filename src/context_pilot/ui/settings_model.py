"""设置界面模型：把配置暴露给设置页面，并处理保存与热键捕获。

设置页分类为：常规（上下文预算 + 行为开关）、模型配置、项目索引、快捷键。
Qt 键码 → 热键字符串的映射只在这里出现，platform/keys.py 保持与 Qt 无关。

列表型数据（模型配置 / 项目索引）不在此文件，见 settings_controller.py。
"""

from dataclasses import replace

from PySide6.QtCore import Property, Qt, QObject, Signal, Slot

from context_pilot.config import Config, load as load_config, save as save_config
from context_pilot.core.shortcuts import (
    NAKED_KEYS,
    ShortcutIssue,
    validate_bindings,
)
from context_pilot.platform import autostart
from context_pilot.platform.keys import HotkeyParseError, format as format_hotkey, is_valid

# 只按修饰键时还不构成热键（Key_Shift/Control/Meta/Alt 属 Qt::Key 专区）
_MODIFIER_KEYS: frozenset[int] = frozenset(
    {int(Qt.Key_Shift), int(Qt.Key_Control), int(Qt.Key_Meta), int(Qt.Key_Alt)}
)

# Win32 修饰符位（与 platform.keys 保持一致）
_MOD_ALT = 0x0001
_MOD_CONTROL = 0x0002
_MOD_SHIFT = 0x0004
_MOD_WIN = 0x0008

# Qt 键码 → Win32 虚拟键码。
# 用 Qt 枚举常量而不是手写数值：Tab / Return / Escape 这类非字母键在 Qt 里用的是
# 0x0100xxxx 专区，**并不等于**它们的 ASCII 值（Key_Return 是 0x01000004 而非 0x0D）。
# 此前写成 0x0D 等 ASCII 值，导致 Ctrl+Enter / Ctrl+Tab 在按下时查不到键码，被判成
# 「无法识别」而永远捕获不到——这类 bug 只在按特定键时才暴露，很难联想到是表写错了。
# 字母与数字恰好与 ASCII 一致，照 range 生成即可。
_QT_TO_VK: dict[int, int] = {
    int(Qt.Key_Space): 0x20,
    int(Qt.Key_Tab): 0x09,
    int(Qt.Key_Backspace): 0x08,
    int(Qt.Key_Return): 0x0D,
    int(Qt.Key_Enter): 0x0D,  # 小键盘回车，与主键盘回车同一个虚拟键
    int(Qt.Key_Escape): 0x1B,
    int(Qt.Key_Insert): 0x2D,
    int(Qt.Key_Delete): 0x2E,
    int(Qt.Key_Home): 0x24,
    int(Qt.Key_End): 0x23,
    int(Qt.Key_PageUp): 0x21,
    int(Qt.Key_PageDown): 0x22,
    int(Qt.Key_Left): 0x25,
    int(Qt.Key_Up): 0x26,
    int(Qt.Key_Right): 0x27,
    int(Qt.Key_Down): 0x28,
}
for _c in range(0x41, 0x5B):  # A-Z
    _QT_TO_VK[_c] = _c
for _c in range(0x30, 0x3A):  # 0-9
    _QT_TO_VK[_c] = _c
for _n in range(1, 25):  # F1-F24
    _QT_TO_VK[int(Qt.Key_F1) + _n - 1] = 0x70 + _n - 1


def qt_key_sequence(
    qt_key: int, qt_modifiers: int, *, allow_naked: bool = False
) -> str:
    """QML 按键 → 热键字符串；不构成合法绑定时返回空串。

    窗口内快捷键与全局热键共用这套转换，避免两处各自维护一份 Qt 键码表。

    ``allow_naked`` 决定是否接受「无修饰键」的单键：全局热键必须带修饰键
    （否则系统层面拦不住普通按键），而窗口内的「关闭」允许绑成 Esc——Esc
    不产生字符，不会跟打字冲突。
    """
    # Qt.KeyboardModifier 是 flag 类型，PySide6 上不能直接 int()，要取 .value
    mask = qt_modifiers
    modifiers = 0
    if mask & Qt.ControlModifier.value:
        modifiers |= _MOD_CONTROL
    if mask & Qt.AltModifier.value:
        modifiers |= _MOD_ALT
    if mask & Qt.ShiftModifier.value:
        modifiers |= _MOD_SHIFT
    if mask & Qt.MetaModifier.value:
        modifiers |= _MOD_WIN

    if qt_key in _MODIFIER_KEYS:
        return ""

    vk = _QT_TO_VK.get(qt_key)
    if vk is None:
        return ""
    try:
        sequence = format_hotkey(modifiers, vk)
    except HotkeyParseError:
        return ""

    # 无修饰键：只有 allow_naked 且落在白名单（Esc / F1-F12）才放行
    if modifiers == 0 and not (allow_naked and sequence in NAKED_KEYS):
        return ""
    return sequence


class SettingsModel(QObject):
    saved = Signal()
    saveFailed = Signal(str)
    hotkeyChanged = Signal(str)
    toggleHotkeyChanged = Signal(str)
    autostartFailed = Signal(str)

    # 下面的"预算/开关"属性同样需要 NOTIFY：QML 对它们做声明式绑定，缺信号时
    # Qt 会打 QQmlExpression「depends on non-bindable properties」警告，
    # 而且属性值变化后绑定不会重新求值（UI 停在旧值上）。
    maxTokensChanged = Signal()
    rulesTokensChanged = Signal()
    memoryTokensChanged = Signal()
    codeTokensChanged = Signal()
    autostartChanged = Signal()
    autoCopyChanged = Signal()
    closeToTrayChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._config: Config = load_config()

    # ---- 快捷键 ----
    def _get_hotkey(self) -> str:
        return self._config.general.hotkey

    def _set_hotkey(self, value: str) -> None:
        sequence = value.strip()
        self._config = _replace_general(self._config, hotkey=sequence)
        self.hotkeyChanged.emit(sequence)

    hotkey = Property(str, _get_hotkey, _set_hotkey, notify=hotkeyChanged)

    def _get_toggle_hotkey(self) -> str:
        """显示/关闭界面的切换热键。"""
        return self._config.general.toggle_hotkey

    def _set_toggle_hotkey(self, value: str) -> None:
        sequence = value.strip()
        self._config = _replace_general(self._config, toggle_hotkey=sequence)
        self.toggleHotkeyChanged.emit(sequence)

    toggleHotkey = Property(
        str, _get_toggle_hotkey, _set_toggle_hotkey, notify=toggleHotkeyChanged
    )

    # ---- 常规：上下文预算 ----
    def _get_max_tokens(self) -> int:
        return self._config.context.max_tokens

    def _set_max_tokens(self, value: int) -> None:
        self._set_context_field("max_tokens", value, self.maxTokensChanged)

    maxTokens = Property(
        int, _get_max_tokens, _set_max_tokens, notify=maxTokensChanged
    )

    def _get_rules_tokens(self) -> int:
        return self._config.context.rules_tokens

    def _set_rules_tokens(self, value: int) -> None:
        self._set_context_field("rules_tokens", value, self.rulesTokensChanged)

    rulesTokens = Property(
        int, _get_rules_tokens, _set_rules_tokens, notify=rulesTokensChanged
    )

    def _get_memory_tokens(self) -> int:
        return self._config.context.memory_tokens

    def _set_memory_tokens(self, value: int) -> None:
        self._set_context_field("memory_tokens", value, self.memoryTokensChanged)

    memoryTokens = Property(
        int, _get_memory_tokens, _set_memory_tokens, notify=memoryTokensChanged
    )

    def _get_code_tokens(self) -> int:
        return self._config.context.code_tokens

    def _set_code_tokens(self, value: int) -> None:
        self._set_context_field("code_tokens", value, self.codeTokensChanged)

    codeTokens = Property(
        int, _get_code_tokens, _set_code_tokens, notify=codeTokensChanged
    )

    # ---- 常规：行为 ----
    def _get_autostart(self) -> bool:
        return self._config.behavior.autostart

    def _set_autostart(self, value: bool) -> None:
        self._set_behavior_field("autostart", value, self.autostartChanged)

    autostart = Property(bool, _get_autostart, _set_autostart, notify=autostartChanged)

    def _get_auto_copy(self) -> bool:
        return self._config.behavior.auto_copy

    def _set_auto_copy(self, value: bool) -> None:
        self._set_behavior_field("auto_copy", value, self.autoCopyChanged)

    autoCopy = Property(bool, _get_auto_copy, _set_auto_copy, notify=autoCopyChanged)

    def _get_close_to_tray(self) -> bool:
        return self._config.behavior.close_to_tray

    def _set_close_to_tray(self, value: bool) -> None:
        self._set_behavior_field("close_to_tray", value, self.closeToTrayChanged)

    closeToTray = Property(
        bool, _get_close_to_tray, _set_close_to_tray, notify=closeToTrayChanged
    )

    def _set_context_field(self, field: str, value: int, signal: Signal) -> None:
        """写 context 的整数字段并在真正变化时发 NOTIFY（值未变不发，免去无谓求值）。"""
        number = int(value)
        if getattr(self._config.context, field) == number:
            return
        self._config = _replace_context(self._config, **{field: number})
        signal.emit()

    def _set_behavior_field(self, field: str, value: bool, signal: Signal) -> None:
        """写 behavior 的布尔字段并在真正变化时发 NOTIFY。"""
        flag = bool(value)
        if getattr(self._config.behavior, field) == flag:
            return
        self._config = _replace_behavior(self._config, **{field: flag})
        signal.emit()

    # ---------- 窗口内快捷键 ----------
    # 读写都走 SettingsModel 是为了让「谁负责写 config.toml」只有一个答案：
    # 全局热键、预算、快捷键最终都由 save() 一次性落盘，不会出现两个Writer
    # 互相覆盖同一段的情况。
    def shortcut_bindings(self) -> dict[str, str]:
        """给主窗口用的绑定表：必定合法（非法值已回退方案默认）。"""
        return self._config.shortcuts.bindings()

    def shortcut_raw(self) -> dict[str, str]:
        """用户实际存下来的绑定表（未修复）。设置页展示与校验都用它——
        展示修复后的值会让「我明明改了却没变」变成一笔糊涂账。"""
        return self._config.shortcuts.raw()

    def shortcut_issues(self) -> list[ShortcutIssue]:
        """当前绑定表的问题清单（error 级会阻断保存）。"""
        return validate_bindings(
            self.shortcut_raw(),
            global_hotkeys=(
                self._config.general.hotkey,
                self._config.general.toggle_hotkey,
            ),
        )

    def set_shortcut_scheme(self, scheme: str) -> dict[str, str]:
        """整套切换方案；返回切换后的绑定表。"""
        self._config = replace(
            self._config, shortcuts=self._config.shortcuts.with_scheme(scheme)
        )
        return self.shortcut_bindings()

    def set_shortcut_binding(self, action: str, sequence: str) -> dict[str, str]:
        """改单个动作的绑定；返回改动后的绑定表。"""
        self._config = replace(
            self._config,
            shortcuts=self._config.shortcuts.with_binding(action, sequence),
        )
        return self.shortcut_bindings()

    def reset_shortcut_action(self, action: str) -> dict[str, str]:
        """把单个动作恢复成当前方案的默认值。"""
        defaults = self._config.shortcuts.with_scheme(
            self._config.shortcuts.scheme
        ).bindings()
        return self.set_shortcut_binding(action, defaults[action])

    # ---------- 配置 ----------
    @property
    def config(self) -> Config:
        """内存中的当前配置（含未保存的编辑），供装配层读取。"""
        return self._config

    # ---- 热键捕获 ----
    @Slot(int, int, result=str)
    def captureHotkey(self, qt_key: int, qt_modifiers: int) -> str:
        """把 QML 传来的 Qt 键码与修饰符转成热键字符串写入增强热键。"""
        return self._apply_capture(qt_key, qt_modifiers, target="hotkey")

    @Slot(str, int, int, result=str)
    def captureHotkeyFor(self, target: str, qt_key: int, qt_modifiers: int) -> str:
        """写入指定热键：hotkey（增强）或 toggle（显示/关闭界面）。"""
        return self._apply_capture(qt_key, qt_modifiers, target=target or "hotkey")

    def _apply_capture(self, qt_key: int, qt_modifiers: int, target: str) -> str:
        """把按键转成热键字符串并落到对应字段；不成组合键时返回空串。"""
        sequence = qt_key_sequence(qt_key, qt_modifiers)
        if not sequence:
            return ""

        if target == "toggle":
            self._config = _replace_general(self._config, toggle_hotkey=sequence)
            self.toggleHotkeyChanged.emit(sequence)
        else:
            self._config = _replace_general(self._config, hotkey=sequence)
            self.hotkeyChanged.emit(sequence)
        return sequence

    @Slot(str, result=bool)
    def validateHotkey(self, sequence: str) -> bool:
        return is_valid(sequence)

    # ---- 保存 ----
    @Slot(result=bool)
    def save(self) -> bool:
        if not is_valid(self._config.general.hotkey):
            self.saveFailed.emit(f"热键不合法：{self._config.general.hotkey}")
            return False
        if not is_valid(self._config.general.toggle_hotkey):
            self.saveFailed.emit(f"界面开关热键不合法：{self._config.general.toggle_hotkey}")
            return False
        # 两个热键相同会互相抢占：注册时后者报「已被占用」，故在此提前拦截
        if self._config.general.hotkey == self._config.general.toggle_hotkey:
            self.saveFailed.emit(
                f"两个快捷键不能相同：{self._config.general.hotkey}"
            )
            return False
        if self._config.context.rules_tokens + self._config.context.memory_tokens \
                + self._config.context.code_tokens > self._config.context.max_tokens:
            self.saveFailed.emit("rules + memory + code 预算之和不能超过总预算 max_tokens")
            return False
        # 窗口内快捷键：error 级问题一律拦下（重复、非组合键、占用编辑组合键）。
        # warning 级（与全局热键相同）不拦——那只是体验瑕疵，用户可自行取舍。
        issues = self.shortcut_issues()
        errors = [i for i in issues if i.level == "error"]
        if errors:
            self.saveFailed.emit(f"窗口快捷键有问题：{errors[0].message}")
            return False

        try:
            save_config(self._config)
            if self._config.behavior.autostart != autostart.is_enabled():
                autostart.apply(self._config.behavior.autostart)
        except OSError as exc:
            self.saveFailed.emit(f"写入配置失败：{exc}")
            return False
        except Exception as exc:  # 注册表写入可能抛出 Windows 专属异常
            self.autostartFailed.emit(f"设置开机自启失败：{exc}")

        self.saved.emit()
        return True


def _replace_general(config: Config, **kw) -> Config:
    return replace(config, general=replace(config.general, **kw))


def _replace_context(config: Config, **kw) -> Config:
    return replace(config, context=replace(config.context, **kw))


def _replace_behavior(config: Config, **kw) -> Config:
    return replace(config, behavior=replace(config.behavior, **kw))
