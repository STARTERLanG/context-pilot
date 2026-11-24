"""记忆候选控制器：把「抽取 → 查重 → 用户确认 → 入库」接到 UI 上。

背景：memory 模块的抽取与查重此前只有测试调用，`MemoryStore.add()` 在生产
代码里零调用点，记忆库恒空。本控制器补上这条链路，且不改既有接口：

- 抽取源用**用户原文**（EnhancedPrompt.original_prompt），不用增强后的任务书
  ——后者是模型改写结果，里面若出现「必须/决定」等词，是模型生成而非用户
  真实意图，抽出来会污染记忆库。
- 候选只在内存里，必须用户逐条确认才写库；查重结果作为提示随候选一起给 UI，
  由用户判断是否仍要保存，控制器不擅自丢弃或覆盖。
- 记忆库按项目根目录哈希隔离，无项目时不抽取（没有归属的记忆没有意义）。

暴露给 QML 的方式与其余控制器一致：setContextProperty + Property/Signal/Slot。
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QObject, Signal, Slot

from context_pilot.core.logging_setup import get_logger
from context_pilot.memory.extractor import CandidateMemory, extract, find_conflicts
from context_pilot.memory.models import MemoryType
from context_pilot.memory.store import MemoryStore

log = get_logger(__name__)

_TYPE_LABELS = {
    MemoryType.PROJECT_FACT: "项目事实",
    MemoryType.ARCHITECTURE_DECISION: "架构决策",
    MemoryType.USER_PREFERENCE: "用户偏好",
    MemoryType.HISTORICAL_DECISION: "历史结论",
}

# 查重提示：超过这个相似度的已有记忆会被标为「可能重复」。与 extractor 默认值一致。
_CONFLICT_THRESHOLD = 0.5


class MemoryController(QObject):
    """记忆候选的持有者与确认入口。每轮增强覆盖上一轮未处理的候选。"""

    candidatesChanged = Signal()
    saved = Signal(int)  # 本次实际写入条数

    def __init__(
        self,
        project_root: str = "",
        *,
        base_dir: Path | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._base_dir = base_dir
        self._project_root = project_root
        self._candidates: list[dict] = []
        # 与候选一一对应的原始类型，确认时按此写库（QML 只拿展示用字典）
        self._types: list[MemoryType] = []

    def _get_candidates(self) -> list[dict]:
        return self._candidates

    candidates = Property("QVariantList", _get_candidates, notify=candidatesChanged)

    @property
    def project_root(self) -> str:
        return self._project_root

    def set_project_root(self, root: str) -> None:
        """切换项目：清空上一项目的候选，避免把 A 项目的决策写进 B 项目。"""
        if root == self._project_root:
            return
        self._project_root = root
        self.clear()

    def _store(self) -> MemoryStore | None:
        if not self._project_root:
            return None
        return MemoryStore(self._project_root, base_dir=self._base_dir)

    @staticmethod
    def _row(candidate: CandidateMemory, conflicts: list[str]) -> dict:
        return {
            "type": _TYPE_LABELS.get(candidate.type, "项目事实"),
            "content": candidate.content,
            "conflicts": conflicts,
            "selected": True,  # 默认全选；用户可在弹窗里取消
        }

    def collect(self, text: str) -> int:
        """从用户原文抽取候选并查重，返回候选数。

        无项目、无候选、记忆库不可用时都返回 0 且不抛——这是增强成功后的
        附带动作，绝不能因为记忆功能故障让主流程报失败。
        """
        candidates = extract(text)
        if not candidates or not self._project_root:
            self.clear()
            return 0
        try:
            store = self._store()
            existing = [m.content for m in store.list()] if store else []
        except Exception as exc:
            log.warning("记忆查重失败，跳过本轮候选：%s", exc)
            self.clear()
            return 0

        rows: list[dict] = []
        types: list[MemoryType] = []
        for candidate in candidates:
            conflicts = find_conflicts(existing, candidate.content, _CONFLICT_THRESHOLD)
            rows.append(self._row(candidate, conflicts))
            types.append(candidate.type)
        self._candidates = rows
        self._types = types
        self.candidatesChanged.emit()
        log.info("抽取到 %d 条记忆候选（项目=%s）", len(rows), self._project_root)
        return len(rows)

    @Slot("QVariantList")
    def confirm(self, selected: list) -> None:
        """写入用户勾选的候选。索引来自 QML 列表序号，越界项直接忽略。"""
        if not self._project_root or not self._candidates:
            return
        picked = {i for i in selected if isinstance(i, int) and 0 <= i < len(self._candidates)}
        if not picked:
            return
        try:
            store = self._store()
            if store is None:
                return
            written = 0
            for index in sorted(picked):
                store.add(
                    self._candidates[index]["content"],
                    memory_type=self._types[index],
                    source="extracted",
                )
                written += 1
        except Exception as exc:
            # UI 边界：写库失败只记日志，不打断主流程；候选保留供重试
            log.warning("记忆写入失败：%s", exc)
            return
        self.clear()
        self.saved.emit(written)
        log.info("已写入 %d 条记忆（项目=%s）", written, self._project_root)

    @Slot()
    def clear(self) -> None:
        """丢弃当前候选（新一轮增强、切换项目、用户关闭弹窗时调用）。"""
        if not self._candidates:
            return
        self._candidates = []
        self._types = []
        self.candidatesChanged.emit()

    @Slot(int, result=bool)
    def toggle(self, index: int) -> bool:
        """切换某条候选的勾选状态，返回切换后的值。QML 列表就地刷新。"""
        if not 0 <= index < len(self._candidates):
            return False
        row = dict(self._candidates[index])
        row["selected"] = not bool(row.get("selected"))
        rows = list(self._candidates)
        rows[index] = row
        self._candidates = rows
        self.candidatesChanged.emit()
        return row["selected"]
