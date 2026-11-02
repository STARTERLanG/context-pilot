"""窗口内快捷键的设置面板数据层；QML 上下文名 `shortcuts`。

职责边界很窄：把 SettingsModel 里的 `[shortcuts]` 配置翻译成 QML 好用的行数据，
并把用户的绑定动作写回去。**写盘不在这里**——保存统一由 SettingsModel.save()
经设置页的「保存」按钮触发，全项目只有那一个出口。

与 PreviewWindow 的关系：主窗口的 Shortcut 项绑定到这里的 `bindings` 属性，
所以改动是即时生效的（无需重启）；保存只是让它在下次启动后依然成立。
"""

from PySide6.QtCore import Property, QObject, Signal, Slot

from context_pilot.core.shortcuts import (
    ACTIONS,
    ACTION_BY_ID,
    DEFAULT_SCHEME,
    SCHEMES,
    SCHEME_BY_ID,
    canonical,
    describe,
    validate_bindings,
    variants,
)
from context_pilot.ui.settings_model import SettingsModel, qt_key_sequence


class ShortcutController(QObject):
    """设置页「窗口快捷键」的数据与动作。

    `bindings` 变化会通知所有依赖它的 QML 表达式，主窗口据此重绑 Shortcut，
    因此不需要「保存后重启」这种粗暴的生效方式。
    """

    bindingsChanged = Signal()
    rejectChanged = Signal()

    def __init__(self, settings: SettingsModel, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._reject = ""

    # ---------- 供主窗口消费 ----------
    def _get_bindings(self) -> dict:
        return self._settings.shortcut_bindings()

    bindings = Property("QVariantMap", _get_bindings, notify=bindingsChanged)

    def _get_sequences(self) -> dict:
        """每个动作要注册的全部写法：动作 id → 字符串列表。

        Enter 与小键盘 Return 在 Qt 里是两个键序列，只注册其中一个会导致
        主键盘能按、小键盘失灵（或反之），所以这里一次给全。
        """
        return {
            action: list(variants(seq))
            for action, seq in self._settings.shortcut_bindings().items()
        }

    sequences = Property("QVariantMap", _get_sequences, notify=bindingsChanged)

    def _get_esc_is_close(self) -> bool:
        """「关闭窗口」是否就绑在 Esc 上。

        主窗口有一条恒定的 Esc 兜底（设置页先退回主页面），若 close 也绑了 Esc，
        两条 Shortcut 会同时触发关窗——用这个标志让两者互斥。
        """
        seq = self._settings.shortcut_bindings().get("close", "")
        return canonical(seq) == "esc"

    escIsClose = Property(bool, _get_esc_is_close, notify=bindingsChanged)

    # ---------- 设置页列表 ----------
    def _current_scheme(self) -> str:
        scheme = self._settings.config.shortcuts.scheme
        return scheme if scheme in SCHEME_BY_ID else DEFAULT_SCHEME

    def _defaults(self) -> dict[str, str]:
        return dict(SCHEME_BY_ID[self._current_scheme()].bindings)

    def _get_scheme(self) -> str:
        return self._current_scheme()

    def _set_scheme(self, value: str) -> None:
        self.setScheme(value)

    scheme = Property(str, _get_scheme, _set_scheme, notify=bindingsChanged)

    def _get_schemes(self) -> list[dict]:
        return [{"id": s.id, "label": s.label, "desc": s.desc} for s in SCHEMES]

    schemes = Property("QVariantList", _get_schemes, notify=bindingsChanged)

    def _get_scheme_labels(self) -> list[str]:
        """方案名列表，直接喂给设置页的 AppSegmented。"""
        return [s.label for s in SCHEMES]

    schemeLabels = Property("QVariantList", _get_scheme_labels, notify=bindingsChanged)

    def _get_scheme_index(self) -> int:
        """当前方案在分段器里的下标；未知方案退回 0（与 _current_scheme 一致）。"""
        current = self._current_scheme()
        for index, scheme in enumerate(SCHEMES):
            if scheme.id == current:
                return index
        return 0

    def _set_scheme_index(self, index: int) -> None:
        if 0 <= index < len(SCHEMES):
            self.setScheme(SCHEMES[index].id)

    schemeIndex = Property(
        int, _get_scheme_index, _set_scheme_index, notify=bindingsChanged
    )

    def _get_scheme_desc(self) -> str:
        return SCHEME_BY_ID[self._current_scheme()].desc

    schemeDesc = Property(str, _get_scheme_desc, notify=bindingsChanged)

    def _get_actions(self) -> list[dict]:
        """每个动作一行：当前值、方案默认值、是否改动过、有无冲突。

        展示的是**用户存下来的原值**（shortcut_raw），不是修复后的值：手改坏
        toml 的人看到的必须是自己写的那个 "u"，配上一句「不是组合键」，而不是
        一个被悄悄换成默认值的框——后者会让人以为自己没改成功。
        """
        bindings = self._settings.shortcut_raw()
        defaults = self._defaults()
        issues = {i.action: i for i in self._settings.shortcut_issues()}
        rows: list[dict] = []
        for action in ACTIONS:
            issue = issues.get(action.id)
            sequence = bindings[action.id]
            rows.append(
                {
                    "id": action.id,
                    "label": action.label,
                    "desc": action.desc,
                    "binding": sequence,
                    "display": describe(sequence),
                    "defaultBinding": defaults[action.id],
                    "modified": sequence != defaults[action.id],
                    "allowNaked": action.allow_naked,
                    "level": issue.level if issue else "",
                    "message": issue.message if issue else "",
                }
            )
        return rows

    actions = Property("QVariantList", _get_actions, notify=bindingsChanged)

    def _get_conflicts(self) -> list[dict]:
        return [
            {"action": i.action, "level": i.level, "message": i.message}
            for i in self._settings.shortcut_issues()
        ]

    conflicts = Property("QVariantList", _get_conflicts, notify=bindingsChanged)

    def _get_has_error(self) -> bool:
        return any(i.level == "error" for i in self._settings.shortcut_issues())

    hasError = Property(bool, _get_has_error, notify=bindingsChanged)

    # ---------- 动作 ----------
    @Slot(str)
    def setScheme(self, scheme: str) -> None:
        """整套切换：一次性替换所有绑定，不存在「改了一半」的中间态。"""
        self._settings.set_shortcut_scheme(scheme)
        self.bindingsChanged.emit()

    @Slot(str)
    def resetAction(self, action: str) -> None:
        """单个动作恢复成当前方案的默认值。"""
        try:
            self._settings.reset_shortcut_action(action)
        except ValueError:
            return
        self.bindingsChanged.emit()

    @Slot()
    def resetAll(self) -> None:
        """全部恢复成当前方案的默认值（保留方案本身不变）。"""
        self._settings.set_shortcut_scheme(self._current_scheme())
        self.bindingsChanged.emit()

    def _get_reject_reason(self) -> str:
        return self._reject

    rejectReason = Property(str, _get_reject_reason, notify=rejectChanged)

    @Slot(str, int, int, result=str)
    def capture(self, action: str, qt_key: int, qt_modifiers: int) -> str:
        """把一次按键绑定到指定动作；成功返回绑定串，不合规则返回空串。

        返回空串时 QML 读 `rejectReason` 拿到具体原因（「与 X 重复」而不是一句
        笼统的「无效」）——用户当场按错，当场就得知道错在哪。

        判定时把这条**试放**进整张表再校验：单看一条只能发现「不是组合键」，
        发现不了「和别的动作撞了」。这正是「重复绑定要提示」的落点。
        """
        self._reject = ""
        target = ACTION_BY_ID.get(action)
        if target is None:
            self._reject = "未知的动作"
            self.rejectChanged.emit()
            return ""

        sequence = qt_key_sequence(qt_key, qt_modifiers, allow_naked=target.allow_naked)
        if not sequence:
            self._reject = (
                "请按 Ctrl / Alt + 键" if not target.allow_naked
                else "请按组合键，或按 Esc"
            )
            self.rejectChanged.emit()
            return ""

        # 归一化写法（enter/return、escape/esc 合一）后再落盘：同一物理键若存成
        # 两种写法，「是否重复绑定」的判断就会出现分歧。
        sequence = canonical(sequence)

        trial = dict(self._settings.shortcut_raw())
        trial[action] = sequence
        blocking = [
            issue for issue in validate_bindings(trial)
            if issue.level == "error" and issue.action == action
        ]
        if blocking:
            self._reject = blocking[0].message
            self.rejectChanged.emit()
            return ""

        try:
            self._settings.set_shortcut_binding(action, sequence)
        except ValueError:
            self._reject = "未知的动作"
            self.rejectChanged.emit()
            return ""
        self.bindingsChanged.emit()
        return sequence

    @Slot(str, result=str)
    def describe(self, sequence: str) -> str:
        """给 QML 用的展示格式化（ctrl+enter → Ctrl+Enter）。"""
        return describe(sequence)

    @Slot()
    def refresh(self) -> None:
        """外部改了配置（如保存后重载）时刷一遍。"""
        self.bindingsChanged.emit()
