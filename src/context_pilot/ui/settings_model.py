"""设置界面模型：把配置与记忆暴露给 QML，并处理保存与热键捕获。

Qt 键码 → 热键字符串的映射只在这里出现，platform/keys.py 保持与 Qt 无关。
"""

from dataclasses import replace

from PySide6.QtCore import Property, QObject, Signal, Slot

from context_pilot.config import Config, LlmConfig, load as load_config, save as save_config
from context_pilot.memory.models import MemoryType
from context_pilot.memory.store import MemoryStore
from context_pilot.platform import autostart
from context_pilot.platform.keys import HotkeyParseError, format as format_hotkey, is_valid

# Qt 键码常量（避免 import Qt 的枚举做位运算）
_QT_CONTROL = 0x04000000
_QT_SHIFT = 0x02000000
_QT_ALT = 0x08000000
_QT_META = 0x10000000

# Win32 修饰符位（与 platform.keys 保持一致）
_MOD_ALT = 0x0001
_MOD_CONTROL = 0x0002
_MOD_SHIFT = 0x0004
_MOD_WIN = 0x0008

_MEMORY_TYPE_LABELS: dict[MemoryType, str] = {
    MemoryType.PROJECT_FACT: "项目事实",
    MemoryType.ARCHITECTURE_DECISION: "架构决策",
    MemoryType.USER_PREFERENCE: "用户偏好",
    MemoryType.HISTORICAL_DECISION: "历史结论",
}

# Qt 键码 → Win32 虚拟键码（仅覆盖可作主键的键）
_QT_TO_VK: dict[int, int] = {
    0x20: 0x20,  # Space
    0x09: 0x09,  # Tab
    0x0D: 0x0D,  # Return
    0x1B: 0x1B,  # Escape
}
for _c in range(0x41, 0x5B):  # A-Z
    _QT_TO_VK[_c] = _c
for _c in range(0x30, 0x3A):  # 0-9
    _QT_TO_VK[_c] = _c
for _n in range(1, 25):  # F1-F24
    _QT_TO_VK[0x01000030 + _n - 1] = 0x70 + _n - 1


class SettingsModel(QObject):
    saved = Signal()
    saveFailed = Signal(str)
    hotkeyChanged = Signal(str)
    memoriesChanged = Signal()
    autostartFailed = Signal(str)

    def __init__(self, project_root, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._project_root = project_root
        self._config: Config = load_config()
        self._store: MemoryStore | None = None
        try:
            self._store = MemoryStore(project_root)
        except OSError:
            self._store = None

    # ---- 通用 ----
    def _get_project_root(self) -> str:
        return self._config.general.project_root

    def _set_project_root(self, value: str) -> None:
        self._config = _replace_general(self._config, project_root=value.strip())

    projectRoot = Property(str, _get_project_root, _set_project_root)

    def _get_hotkey(self) -> str:
        return self._config.general.hotkey

    hotkey = Property(str, _get_hotkey)

    def _get_agent(self) -> str:
        return self._config.general.agent

    def _set_agent(self, value: str) -> None:
        self._config = _replace_general(self._config, agent=value)

    agent = Property(str, _get_agent, _set_agent)

    # ---- 模型 ----
    def _get_provider(self) -> str:
        return self._config.llm.provider

    def _set_provider(self, value: str) -> None:
        self._config = _replace_llm(self._config, provider=value)

    provider = Property(str, _get_provider, _set_provider)

    def _get_base_url(self) -> str:
        return self._config.llm.base_url

    def _set_base_url(self, value: str) -> None:
        self._config = _replace_llm(self._config, base_url=value.strip())

    baseUrl = Property(str, _get_base_url, _set_base_url)

    def _get_api_key(self) -> str:
        return self._config.llm.api_key

    def _set_api_key(self, value: str) -> None:
        self._config = _replace_llm(self._config, api_key=value.strip())

    apiKey = Property(str, _get_api_key, _set_api_key)

    def _get_model(self) -> str:
        return self._config.llm.model

    def _set_model(self, value: str) -> None:
        self._config = _replace_llm(self._config, model=value.strip())

    model = Property(str, _get_model, _set_model)

    def _get_timeout(self) -> float:
        return self._config.llm.timeout

    def _set_timeout(self, value: float) -> None:
        self._config = _replace_llm(self._config, timeout=float(value))

    timeout = Property(float, _get_timeout, _set_timeout)

    # ---- 上下文预算 ----
    def _get_max_tokens(self) -> int:
        return self._config.context.max_tokens

    def _set_max_tokens(self, value: int) -> None:
        self._config = _replace_context(self._config, max_tokens=int(value))

    maxTokens = Property(int, _get_max_tokens, _set_max_tokens)

    def _get_rules_tokens(self) -> int:
        return self._config.context.rules_tokens

    def _set_rules_tokens(self, value: int) -> None:
        self._config = _replace_context(self._config, rules_tokens=int(value))

    rulesTokens = Property(int, _get_rules_tokens, _set_rules_tokens)

    def _get_memory_tokens(self) -> int:
        return self._config.context.memory_tokens

    def _set_memory_tokens(self, value: int) -> None:
        self._config = _replace_context(self._config, memory_tokens=int(value))

    memoryTokens = Property(int, _get_memory_tokens, _set_memory_tokens)

    def _get_code_tokens(self) -> int:
        return self._config.context.code_tokens

    def _set_code_tokens(self, value: int) -> None:
        self._config = _replace_context(self._config, code_tokens=int(value))

    codeTokens = Property(int, _get_code_tokens, _set_code_tokens)

    # ---- 记忆 ----
    def _get_memory_enabled(self) -> bool:
        return self._config.memory.enabled

    def _set_memory_enabled(self, value: bool) -> None:
        self._config = _replace_memory(self._config, enabled=bool(value))

    memoryEnabled = Property(bool, _get_memory_enabled, _set_memory_enabled)

    def _get_memories(self) -> list[dict]:
        if self._store is None:
            return []
        return [
            {
                "id": memory.id,
                "type": _MEMORY_TYPE_LABELS.get(memory.type, memory.type.value),
                "content": memory.content,
                "createdAt": memory.created_at,
            }
            for memory in self._store.list()
        ]

    memories = Property("QVariantList", _get_memories, notify=memoriesChanged)

    # ---- 行为 ----
    def _get_autostart(self) -> bool:
        return self._config.behavior.autostart

    def _set_autostart(self, value: bool) -> None:
        self._config = _replace_behavior(self._config, autostart=bool(value))

    autostart = Property(bool, _get_autostart, _set_autostart)

    def _get_auto_copy(self) -> bool:
        return self._config.behavior.auto_copy

    def _set_auto_copy(self, value: bool) -> None:
        self._config = _replace_behavior(self._config, auto_copy=bool(value))

    autoCopy = Property(bool, _get_auto_copy, _set_auto_copy)

    def _get_close_to_tray(self) -> bool:
        return self._config.behavior.close_to_tray

    def _set_close_to_tray(self, value: bool) -> None:
        self._config = _replace_behavior(self._config, close_to_tray=bool(value))

    closeToTray = Property(bool, _get_close_to_tray, _set_close_to_tray)

    # ---- 热键捕获 ----
    @Slot(int, int, result=str)
    def captureHotkey(self, qt_key: int, qt_modifiers: int) -> str:
        """把 QML 传来的 Qt 键码与修饰符转成热键字符串；不合法返回空串。"""
        modifiers = 0
        if qt_modifiers & _QT_CONTROL:
            modifiers |= _MOD_CONTROL
        if qt_modifiers & _QT_ALT:
            modifiers |= _MOD_ALT
        if qt_modifiers & _QT_SHIFT:
            modifiers |= _MOD_SHIFT
        if qt_modifiers & _QT_META:
            modifiers |= _MOD_WIN

        # 只按修饰键，尚不构成完整热键
        if qt_key in (0x01000021, 0x01000020, 0x01000023, 0x01000022):  # Ctrl/Shift/Alt/Meta
            return ""

        vk = _QT_TO_VK.get(qt_key)
        if vk is None or modifiers == 0:
            return ""
        try:
            sequence = format_hotkey(modifiers, vk)
        except HotkeyParseError:
            return ""
        self._config = _replace_general(self._config, hotkey=sequence)
        self.hotkeyChanged.emit(sequence)
        return sequence

    @Slot(str, result=bool)
    def validateHotkey(self, sequence: str) -> bool:
        return is_valid(sequence)

    # ---- 保存与记忆操作 ----
    @Slot(result=bool)
    def save(self) -> bool:
        if not is_valid(self._config.general.hotkey):
            self.saveFailed.emit(f"热键不合法：{self._config.general.hotkey}")
            return False
        if self._config.context.rules_tokens + self._config.context.memory_tokens \
                + self._config.context.code_tokens > self._config.context.max_tokens:
            self.saveFailed.emit("rules + memory + code 预算之和不能超过总预算 max_tokens")
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

    @Slot(str)
    def deleteMemory(self, memory_id: str) -> None:
        if self._store is not None and self._store.delete(memory_id):
            self.memoriesChanged.emit()

    @Slot()
    def reloadMemories(self) -> None:
        self.memoriesChanged.emit()


def _replace_general(config: Config, **kw) -> Config:
    return replace(config, general=replace(config.general, **kw))


def _replace_llm(config: Config, **kw) -> Config:
    return replace(config, llm=replace(config.llm, **kw))


def _replace_memory(config: Config, **kw) -> Config:
    return replace(config, memory=replace(config.memory, **kw))


def _replace_context(config: Config, **kw) -> Config:
    return replace(config, context=replace(config.context, **kw))


def _replace_behavior(config: Config, **kw) -> Config:
    return replace(config, behavior=replace(config.behavior, **kw))
