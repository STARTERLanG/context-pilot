"""暴露给 QML 的预览数据模型。

只读展示 + 动作槽，用 setContextProperty 注入。Diff 与 token 统计在
Python 侧算好（core/diff、core/tokens），QML 只负责渲染。

历史记录为会话级（内存态）：记录每次增强的原始指令与增强结果，供
「历史记录」按钮回看；进程重启即清空，不落盘。
"""

from datetime import datetime

from PySide6.QtCore import Property, QObject, Signal, Slot

from context_pilot.adapters.base import AgentAdapter

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
    sessionStarted = Signal()  # 仅新会话开始时触发（begin）
    useRequested = Signal(str)
    closeRequested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._adapter: AgentAdapter | None = None
        self._original = ""
        self._enhanced = ""
        self._context: list[str] = []
        self._status = "就绪"
        self._token_stats: dict = {"original": 0, "context": 0, "enhanced": 0, "total": 0}
        self._diff_rows: list[dict] = []
        self._context_rows: list[dict] = []
        # 会话级历史：[(时间戳, 原始指令, 增强结果), ...]，新条目在前
        self._history: list[dict] = []

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

    def _get_history(self) -> list[dict]:
        return self._history

    originalPrompt = Property(str, _get_original, notify=changed)
    enhancedPrompt = Property(str, _get_enhanced, notify=changed)
    contextFiles = Property("QVariantList", _get_context, notify=changed)
    status = Property(str, _get_status, notify=changed)
    tokenStats = Property("QVariantMap", _get_token_stats, notify=changed)
    diffRows = Property("QVariantList", _get_diff_rows, notify=changed)
    contextRows = Property("QVariantList", _get_context_rows, notify=changed)
    history = Property("QVariantList", _get_history, notify=changed)

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
        self.sessionStarted.emit()

    def set_result(self, result: EnhancedPrompt) -> None:
        self._original = result.original_prompt
        self._enhanced = result.enhanced_prompt
        self._context = [item.path or item.source for item in result.context]
        self._status = "完成"
        self._token_stats = _token_stats(result)
        self._diff_rows = _diff_rows(result.original_prompt, result.enhanced_prompt)
        self._context_rows = _context_rows(result.context)
        self._record_history(result.original_prompt, result.enhanced_prompt)
        self.changed.emit()

    def set_failed(self, message: str) -> None:
        self._status = f"失败：{message}"
        self.changed.emit()

    def set_adapter(self, adapter: AgentAdapter) -> None:
        self._adapter = adapter

    def _record_history(self, original: str, enhanced: str) -> None:
        """追加一条历史记录（会话级，重启清空）。"""
        stamp = datetime.now().strftime("%H:%M:%S")
        self._history.insert(0, {
            "time": stamp,
            "original": original,
            "enhanced": enhanced,
        })

    @Slot(str)
    def use(self, text: str) -> None:
        self._enhanced = text
        self.useRequested.emit(text)

    @Slot(str, result=bool)
    def sendToAgent(self, text: str) -> bool:
        """把文本交给当前 Agent 适配器。返回是否已发出。"""
        if self._adapter is None:
            return False
        try:
            self._adapter.deliver(text)
        except Exception:  # 剪贴板写入失败等，UI 边界吞掉并返回失败
            return False
        return True

    @Slot()
    def close(self) -> None:
        self.closeRequested.emit()
