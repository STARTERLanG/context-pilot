"""暴露给 QML 的预览数据模型。

只读展示 + 动作槽，用 setContextProperty 注入。Diff 与 token 统计在
Python 侧算好（core/diff、core/tokens），QML 只负责渲染。

历史记录为会话级（内存态）：记录每次增强的原始指令与增强结果，供
「历史记录」按钮回看；进程重启即清空，不落盘。
"""

from datetime import datetime

from PySide6.QtCore import Property, QObject, Signal, Slot

from context_pilot.adapters.base import AgentAdapter

from context_pilot.core.diff import compare
from context_pilot.core.models import ContextItem, EnhancedPrompt
from context_pilot.core.tokens import estimate


def _token_stats(result: EnhancedPrompt) -> dict:
    """各项 token 用量。budget 是本次生效的上下文预算上限，供 UI 算占比。"""
    return {
        "original": estimate(result.original_prompt),
        "context": sum(estimate(item.content) for item in result.context),
        "enhanced": estimate(result.enhanced_prompt),
        "total": (
            estimate(result.original_prompt)
            + sum(estimate(item.content) for item in result.context)
            + estimate(result.enhanced_prompt)
        ),
        "budget": result.budget_tokens,
    }


def _context_rows(items: list[ContextItem]) -> list[dict]:
    """把上下文项转成 QML 可直接展示的行。

    每条行携带命中的精确片段（snippet）与行号区间，供「上下文检查器」
    点击文件时展示具体被选中的代码/文本，而非只显示文件名。
    """
    return [
        {
            "source": item.source,
            "type": item.type,
            "reason": item.reason or "—",
            "relevance": f"{item.relevance:.2f}",
            "tokens": estimate(item.content),
            "snippet": item.snippet or item.content,
            "lineStart": item.line_start or 0,
            "lineEnd": item.line_end or 0,
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
    sessionStarted = Signal()  # 仅新会话开始时触发（begin / load）
    # 仅增强成功时触发。QML 据此把结果填进可编辑的结果框——不能用 changed，
    # 因为 set_failed 也会发 changed，会把框里用户正在编辑的内容冲掉。
    resultReady = Signal()
    useRequested = Signal(str)
    enhanceRequested = Signal(str)  # 用户手动点「增强」按钮，请求后端跑管线
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
        # 单调递增的条目序号：界面用它标识「展开的是哪一条」。
        # 不能用列表下标——新记录插在最前，下标会整体后移，展开的就成了别的条目。
        self._history_seq = 0
        # 增强进行中标志：防重复点击（问题 3）。增强完成/失败时复位。
        self._enhancing = False
        # 上一次真正提交给管线的原文：「重新增强」用它，而不是输入框当前内容——
        # 否则用户在结果框/输入框里改过字之后，rerun 跑的就不是原来那一次。
        self._last_submitted = ""

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

    def _get_enhancing(self) -> bool:
        return self._enhancing

    def _get_over_budget(self) -> bool:
        """本次是否超出上下文预算。

        预算为 0（未配置/未知）时一律 False——没有上限就谈不上超限，
        不能让 UI 显示 "超预算 inf%"。
        """
        budget = self._token_stats.get("budget", 0)
        return budget > 0 and self._token_stats.get("total", 0) > budget

    originalPrompt = Property(str, _get_original, notify=changed)
    enhancedPrompt = Property(str, _get_enhanced, notify=changed)
    contextFiles = Property("QVariantList", _get_context, notify=changed)
    status = Property(str, _get_status, notify=changed)
    tokenStats = Property("QVariantMap", _get_token_stats, notify=changed)
    diffRows = Property("QVariantList", _get_diff_rows, notify=changed)
    contextRows = Property("QVariantList", _get_context_rows, notify=changed)
    history = Property("QVariantList", _get_history, notify=changed)
    enhancing = Property(bool, _get_enhancing, notify=changed)
    overBudget = Property(bool, _get_over_budget, notify=changed)

    def begin(self, prompt: str) -> None:
        """开始一次增强：清空旧结果，显示原 prompt。"""
        self._original = prompt
        self._enhanced = ""
        self._context = []
        self._status = "正在增强…"
        # budget 沿用上一次的值：它来自项目/配置而非本次增强，清空会让状态栏
        # 在增强期间闪一下「无预算」
        self._token_stats = {
            "original": estimate(prompt),
            "context": 0,
            "enhanced": 0,
            "total": 0,
            "budget": self._token_stats.get("budget", 0),
        }
        self._diff_rows = []
        self._context_rows = []
        self.changed.emit()
        self.sessionStarted.emit()

    def load(self, prompt: str) -> None:
        """仅把原始指令载入输入框，不触发增强。

        取消「自动增强」后的入口：热键/托盘只负责把剪贴板内容放进来展示，
        增强交由用户手动点「增强」按钮。状态保持「就绪」，输入框原样显示。
        """
        self._original = prompt
        self._enhanced = ""
        self._context = []
        self._status = "就绪"
        self._token_stats = {"original": estimate(prompt), "context": 0, "enhanced": 0, "total": 0}
        self._diff_rows = []
        self._context_rows = []
        self.changed.emit()
        self.sessionStarted.emit()

    @Slot(str)
    def enhance(self, text: str) -> None:
        """「增强」按钮：以输入框当前内容发起一次增强（begin + 通知后端）。

        防重复点击：增强进行中时直接忽略后续触发，避免同一指令被并发处理
        多次、结果乱序覆盖（问题 3）。
        """
        if not text.strip():
            self.set_failed("指令为空")
            return
        if self._enhancing:
            return
        self._enhancing = True
        self._last_submitted = text
        self.begin(text)
        self.enhanceRequested.emit(text)

    @Slot()
    def rerun(self) -> None:
        """「重新增强」：以**上一次提交的原文**再跑一次。

        与 enhance() 的区别就在输入来源：enhance 取输入框当前内容，rerun 取
        上次提交的原文。用户在输入框里改了字又想重跑旧的那次时，这两个语义
        不能混——否则「重跑一次看会不会更好」这件事会因为手滑改过一个字而
        变得不可复现。
        """
        if not self._last_submitted.strip():
            self.set_failed("还没有可重跑的指令")
            return
        if self._enhancing:
            return
        self._enhancing = True
        self.begin(self._last_submitted)
        self.enhanceRequested.emit(self._last_submitted)

    def set_result(self, result: EnhancedPrompt) -> None:
        self._enhancing = False
        self._original = result.original_prompt
        self._enhanced = result.enhanced_prompt
        self._context = [item.path or item.source for item in result.context]
        self._status = "完成"
        self._token_stats = _token_stats(result)
        self._diff_rows = _diff_rows(result.original_prompt, result.enhanced_prompt)
        self._context_rows = _context_rows(result.context)
        self._record_history(result.original_prompt, result.enhanced_prompt)
        self.changed.emit()
        self.resultReady.emit()

    def set_failed(self, message: str) -> None:
        self._enhancing = False
        self._status = f"失败：{message}"
        self.changed.emit()

    def set_adapter(self, adapter: AgentAdapter) -> None:
        self._adapter = adapter

    def _record_history(self, original: str, enhanced: str) -> None:
        """追加一条历史记录（会话级，重启清空）。"""
        stamp = datetime.now().strftime("%H:%M:%S")
        self._history_seq += 1
        self._history.insert(0, {
            "key": self._history_seq,
            "time": stamp,
            "original": original,
            "enhanced": enhanced,
        })

    @Slot(str)
    def use(self, text: str) -> None:
        """「使用增强结果」：以**结果框当前内容**为准（PRD 第三十八章 Edit）。

        text 由 QML 传入编辑后的实际文本，而非模型里保存的原始增强结果——
        否则用户手动改过的内容会被丢弃。同步回模型后，后续的复制、发送
        到 Agent 也一并使用编辑后的版本。
        """
        if not text.strip():
            return
        self._enhanced = text
        # 编辑会改变长度，刷新增强项与合计的 token 统计，保持状态栏一致
        self._token_stats = {
            **self._token_stats,
            "enhanced": estimate(text),
            "total": (
                self._token_stats.get("original", 0)
                + self._token_stats.get("context", 0)
                + estimate(text)
            ),
        }
        self.useRequested.emit(text)

    @Slot(str, result=bool)
    def copyText(self, text: str) -> bool:
        """复制文本到剪贴板。返回是否成功。"""
        from context_pilot.platform.clipboard import write_clipboard_text

        if not text:
            return False
        try:
            write_clipboard_text(text)
        except Exception:  # UI 边界：剪贴板不可用时返回失败，不抛
            return False
        return True

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
