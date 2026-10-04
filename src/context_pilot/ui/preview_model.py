"""暴露给 QML 的预览数据模型。

只读展示 + 动作槽，用 setContextProperty 注入。Diff 与 token 统计在
Python 侧算好（core/diff、core/tokens），QML 只负责渲染。
"""

from PySide6.QtCore import Property, QObject, Signal, Slot

from context_pilot.core.diff import KIND_ADDED, KIND_REMOVED, compare
from context_pilot.core.models import ContextItem, EnhancedPrompt
from context_pilot.core.tokens import estimate


def _token_stats(result: EnhancedPrompt) -> dict:
    return {
        "original": estimate(result.original_prompt),
        "context": sum(estimate(item.content) for item in result.context),
        "enhanced": estimate(result.enhanced_prompt),
        "total": (
            estimate(result.original_prompt)
            + sum(estimate(item.content) for item in result.context)
            + estimate(result.enhanced_prompt)
        ),
    }


def _context_rows(items: list[ContextItem]) -> list[dict]:
    """把上下文项转成 QML 可直接展示的行。"""
    return [
        {
            "source": item.source,
            "type": item.type,
            "reason": item.reason or "—",
            "relevance": f"{item.relevance:.2f}",
            "tokens": estimate(item.content),
        }
        for item in items
    ]


def _diff_rows(original: str, enhanced: str) -> list[dict]:
    return [
        {"kind": line.kind, "text": line.text, "oldLine": line.old_line, "newLine": line.new_line}
        for line in compare(original, enhanced)
    ]


class PreviewModel(QObject):
    changed = Signal()
    useRequested = Signal(str)
    closeRequested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._original = ""
        self._enhanced = ""
        self._context: list[str] = []
        self._status = "就绪"
        self._token_stats: dict = {"original": 0, "context": 0, "enhanced": 0, "total": 0}
        self._diff_rows: list[dict] = []
        self._context_rows: list[dict] = []

    def _get_original(self) -> str:
        return self._original

    def _get_enhanced(self) -> str:
        return self._enhanced

    def _get_context(self) -> list[str]:
        return self._context

    def _get_status(self) -> str:
        return self._status

    def _get_token_stats(self) -> dict:
        return self._token_stats

    def _get_diff_rows(self) -> list[dict]:
        return self._diff_rows

    def _get_context_rows(self) -> list[dict]:
        return self._context_rows

    originalPrompt = Property(str, _get_original, notify=changed)
    enhancedPrompt = Property(str, _get_enhanced, notify=changed)
    contextFiles = Property("QVariantList", _get_context, notify=changed)
    status = Property(str, _get_status, notify=changed)
    tokenStats = Property("QVariantMap", _get_token_stats, notify=changed)
    diffRows = Property("QVariantList", _get_diff_rows, notify=changed)
    contextRows = Property("QVariantList", _get_context_rows, notify=changed)

    def begin(self, prompt: str) -> None:
        """开始一次增强：清空旧结果，显示原 prompt。"""
        self._original = prompt
        self._enhanced = ""
        self._context = []
        self._status = "正在增强…"
        self._token_stats = {"original": estimate(prompt), "context": 0, "enhanced": 0, "total": 0}
        self._diff_rows = []
        self._context_rows = []
        self.changed.emit()

    def set_result(self, result: EnhancedPrompt) -> None:
        self._original = result.original_prompt
        self._enhanced = result.enhanced_prompt
        self._context = [item.path or item.source for item in result.context]
        self._status = "完成"
        self._token_stats = _token_stats(result)
        self._diff_rows = _diff_rows(result.original_prompt, result.enhanced_prompt)
        self._context_rows = _context_rows(result.context)
        self.changed.emit()

    def set_failed(self, message: str) -> None:
        self._status = f"失败：{message}"
        self.changed.emit()

    @Slot(str)
    def use(self, text: str) -> None:
        self._enhanced = text
        self.useRequested.emit(text)

    @Slot()
    def close(self) -> None:
        self.closeRequested.emit()
