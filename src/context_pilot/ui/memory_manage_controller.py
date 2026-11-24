"""设置页「记忆管理」控制器：分别列出 / 编辑 / 删除项目记忆与全局记忆。

与 MemoryController（候选抽取确认）职责分开：那个管「新记忆怎么进来」，
这个管「已存记忆怎么看、怎么改」。两类记忆物理上分库存放，UI 用 scope
字段区分展示；任何写操作后立即刷新列表，保证展示结果与磁盘一致。

项目记忆按「设置页选定的项目」查看，不混合展示所有项目：
- 下拉候选来自 ProjectStore（全部已索引项目 + 「无项目」）；
- 选定项目后只读该项目的库；未手动选择时跟随装配层同步进来的当前项目；
- 全局记忆独立于项目，任何选择下都完整展示。
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QObject, Signal, Slot

from context_pilot.core.logging_setup import get_logger
from context_pilot.memory.models import MemoryType
from context_pilot.memory.store import MemoryStore
from context_pilot.projects.projects import ProjectStore

log = get_logger(__name__)

_TYPE_LABELS = {
    MemoryType.PROJECT_FACT: "项目事实",
    MemoryType.ARCHITECTURE_DECISION: "架构决策",
    MemoryType.USER_PREFERENCE: "用户偏好",
    MemoryType.HISTORICAL_DECISION: "历史结论",
}
_TYPE_VALUES = {label: value for value, label in _TYPE_LABELS.items()}

_SCOPE_PROJECT = "project"
_SCOPE_GLOBAL = "global"
# 「无项目」：与 SessionController 的 DEFAULT_PROJECT_ID 语义一致，不对应任何库
_NO_PROJECT_ID = "default"


class MemoryManageController(QObject):
    """记忆管理列表与 CRUD。每次写操作后 emit 对应 Changed 信号。"""

    projectMemoriesChanged = Signal()
    globalMemoriesChanged = Signal()
    projectsChanged = Signal()
    selectedProjectChanged = Signal()
    errorChanged = Signal()

    def __init__(
        self,
        project_root: str = "",
        *,
        base_dir: Path | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._base_dir = base_dir
        # 主窗口当前项目路径：仅在用户未于设置页手动选择前作为初始值
        self._project_root = project_root
        self._selected_project_id = ""
        self._project_memories: list[dict] = []
        self._global_memories: list[dict] = []
        self._projects: list[dict] = []
        self._error = ""
        self.refresh()

    # ---------- QML 属性 ----------
    def _get_project_memories(self) -> list[dict]:
        return self._project_memories

    def _get_global_memories(self) -> list[dict]:
        return self._global_memories

    def _get_project_names(self) -> list[str]:
        return [item["name"] for item in self._projects]

    def _get_selected_project(self) -> str:
        # 手动选择优先；否则跟随主窗口当前项目对应的候选项
        if self._selected_project_id:
            for item in self._projects:
                if item["id"] == self._selected_project_id:
                    return item["name"]
        for item in self._projects:
            if item["path"] == self._project_root:
                return item["name"]
        return self._projects[0]["name"] if self._projects else ""

    def _get_error(self) -> str:
        return self._error

    projectMemories = Property("QVariantList", _get_project_memories, notify=projectMemoriesChanged)
    globalMemories = Property("QVariantList", _get_global_memories, notify=globalMemoriesChanged)
    projects = Property("QStringList", _get_project_names, notify=projectsChanged)
    selectedProject = Property(str, _get_selected_project, notify=selectedProjectChanged)
    error = Property(str, _get_error, notify=errorChanged)

    @property
    def project_root(self) -> str:
        return self._project_root

    def set_project_root(self, root: str) -> None:
        """装配层同步主窗口项目。用户已在设置页手动选择时不再覆盖其选择。"""
        if root == self._project_root:
            return
        self._project_root = root
        self.refresh()
        self.selectedProjectChanged.emit()

    def _set_error(self, message: str) -> None:
        if self._error == message:
            return
        self._error = message
        self.errorChanged.emit()

    # ---------- 项目选择 ----------
    def _load_projects(self) -> None:
        items = [{"id": _NO_PROJECT_ID, "name": "无项目", "path": ""}]
        try:
            entries = ProjectStore(base_dir=self._base_dir).list()
        except OSError as exc:
            self._set_error(f"读取项目列表失败：{exc}")
            entries = []
        for entry in entries:
            items.append(
                {
                    "id": entry.id,
                    "name": entry.name or Path(entry.path).name or entry.path,
                    "path": entry.path,
                }
            )
        self._projects = items
        self.projectsChanged.emit()

    def _active_project_path(self) -> str:
        """当前查看的项目路径：手动选择 > 主窗口同步 > 无项目。"""
        if self._selected_project_id:
            for item in self._projects:
                if item["id"] == self._selected_project_id:
                    return item["path"]
            return ""
        return self._project_root

    @Slot(str)
    def selectProjectByName(self, name: str) -> None:
        """下拉选中一个项目名：项目记忆栏只展示该项目的记忆。"""
        matched = _NO_PROJECT_ID
        for item in self._projects:
            if item["name"] == name:
                matched = item["id"]
                break
        if matched == self._selected_project_id:
            return
        self._selected_project_id = matched
        self._set_error("")
        self.selectedProjectChanged.emit()
        self.refresh()

    # ---------- 读取 ----------
    @staticmethod
    def _rows(store: MemoryStore | None) -> list[dict]:
        if store is None:
            return []
        try:
            memories = store.list()
        except OSError as exc:
            log.warning("读取记忆库失败：%s", exc)
            return []
        return [
            {
                "id": m.id,
                "type": _TYPE_LABELS.get(m.type, "项目事实"),
                "content": m.content,
                "scope": m.scope,
                "createdAt": m.created_at,
                "updatedAt": m.updated_at,
            }
            for m in memories
        ]

    @Slot()
    def refresh(self) -> None:
        """重读项目列表与两栏记忆。任何 CRUD 后都调用，保证界面与磁盘一致。"""
        self._load_projects()
        project_store = None
        project_path = self._active_project_path()
        if project_path:
            try:
                project_store = MemoryStore(
                    project_path, base_dir=self._base_dir, scope=_SCOPE_PROJECT
                )
            except OSError as exc:
                self._set_error(f"打开项目记忆库失败：{exc}")
        try:
            global_store = MemoryStore("", base_dir=self._base_dir, scope=_SCOPE_GLOBAL)
        except OSError as exc:
            self._set_error(f"打开全局记忆库失败：{exc}")
            global_store = None

        self._project_memories = self._rows(project_store)
        self._global_memories = self._rows(global_store)
        self.projectMemoriesChanged.emit()
        self.globalMemoriesChanged.emit()

    # ---------- 写入 ----------
    def _store_for(self, scope: str) -> MemoryStore | None:
        try:
            if scope == _SCOPE_GLOBAL:
                return MemoryStore("", base_dir=self._base_dir, scope=_SCOPE_GLOBAL)
            project_path = self._active_project_path()
            if not project_path:
                self._set_error("未选中项目，无法保存项目记忆")
                return None
            return MemoryStore(
                project_path, base_dir=self._base_dir, scope=_SCOPE_PROJECT
            )
        except OSError as exc:
            self._set_error(f"打开记忆库失败：{exc}")
            return None

    @Slot(str, str, str)
    def add(self, scope: str, content: str, type_label: str) -> None:
        """新增记忆。scope 取 project/global，type_label 取中文类型名。"""
        text = content.strip()
        if not text:
            self._set_error("记忆内容不能为空")
            return
        store = self._store_for(scope)
        if store is None:
            return
        memory_type = _TYPE_VALUES.get(type_label, MemoryType.PROJECT_FACT)
        try:
            store.add(text, memory_type=memory_type, source="manual")
        except (OSError, ValueError) as exc:
            self._set_error(f"保存记忆失败：{exc}")
            return
        self._set_error("")
        self.refresh()

    @Slot(str, str, str, str)
    def update(self, scope: str, memory_id: str, content: str, type_label: str) -> None:
        """编辑记忆，成功后立即刷新（QML 绑定同一个 Property 自动更新）。"""
        text = content.strip()
        if not text:
            self._set_error("记忆内容不能为空")
            return
        store = self._store_for(scope)
        if store is None:
            return
        memory_type = _TYPE_VALUES.get(type_label, None)
        try:
            ok = store.update(memory_id, text, memory_type)
        except (OSError, ValueError) as exc:
            self._set_error(f"修改记忆失败：{exc}")
            return
        if not ok:
            self._set_error("记忆不存在或已被删除")
            return
        self._set_error("")
        self.refresh()

    @Slot(str, str)
    def delete(self, scope: str, memory_id: str) -> None:
        """删除记忆，成功后立即刷新。"""
        store = self._store_for(scope)
        if store is None:
            return
        try:
            ok = store.delete(memory_id)
        except OSError as exc:
            self._set_error(f"删除记忆失败：{exc}")
            return
        if not ok:
            self._set_error("记忆不存在或已被删除")
            return
        self._set_error("")
        self.refresh()
