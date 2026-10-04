"""暴露给 QML 的预览数据模型。

只读展示 + 两个动作槽，用 setContextProperty 注入即可，无需 ListModel。
"""

from PySide6.QtCore import Property, QObject, Signal, Slot

from context_pilot.core.models import EnhancedPrompt


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

    def _get_original(self) -> str:
        return self._original

    def _get_enhanced(self) -> str:
        return self._enhanced

    def _get_context(self) -> list[str]:
        return self._context

    def _get_status(self) -> str:
        return self._status

    originalPrompt = Property(str, _get_original, notify=changed)
    enhancedPrompt = Property(str, _get_enhanced, notify=changed)
    contextFiles = Property("QVariantList", _get_context, notify=changed)
    status = Property(str, _get_status, notify=changed)

    def begin(self, prompt: str) -> None:
        """开始一次增强：清空旧结果，显示原 prompt。"""
        self._original = prompt
        self._enhanced = ""
        self._context = []
        self._status = "正在增强…"
        self.changed.emit()

    def set_result(self, result: EnhancedPrompt) -> None:
        self._original = result.original_prompt
        self._enhanced = result.enhanced_prompt
        self._context = [item.path or item.source for item in result.context]
        self._status = "完成"
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
