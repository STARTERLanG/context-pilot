"""设置页（QML）控制层：模型配置与项目索引的 CRUD + 后台任务。

原先 QWidget 版设置窗把这些逻辑写在 SettingsWindow 里；改为窗内页面后，UI 只
负责渲染，交互全部经本控制层的槽完成，方便单元测试（构造时传 base_dir 隔离）。

职责边界：
- 预算类与开关类字段仍由 SettingsModel 暴露（QML 直接双向绑定），本类不重复；
- 列表型数据（模型配置 / 项目索引）以 QVariantList 属性暴露给 QML 的 Repeater；
- 网络与磁盘扫描类操作走 QThread，结果以信号回传，避免阻塞主线程。
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QObject, QThread, Signal, Slot

from context_pilot.models.profiles import ProfileStore
from context_pilot.models.styles import StyleStore
from context_pilot.projects.indexer import Indexer
from context_pilot.projects.projects import ProjectStore
from context_pilot.ui.settings_model import SettingsModel
from context_pilot.ui.worker import ModelsFetchThread

# 项目索引状态 → 中文文案（PYTHON 侧统一，避免 QML 里散落状态判断）
_STATUS_TEXT = {
    "pending": "未创建",
    "running": "创建中",
    "done": "已完成",
    "failed": "失败",
}


class _TestThread(QThread):
    """单个模型配置的连通性测试。"""

    succeeded = Signal(float)
    failed = Signal(str)

    def __init__(
        self, base_url: str, api_key: str, model: str, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._base_url = base_url
        self._api_key = api_key
        self._model = model

    def run(self) -> None:
        from context_pilot.optimizer.openai_provider import check_connection

        try:
            elapsed = check_connection(self._base_url, self._api_key, self._model)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(float(elapsed))


class _IndexThread(QThread):
    """构建单个项目的索引（磁盘遍历，耗时）。"""

    def __init__(
        self,
        indexer: Indexer,
        entry,
        store: ProjectStore,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._indexer = indexer
        self._entry = entry
        self._store = store

    def run(self) -> None:
        from context_pilot.projects.projects import STATUS_FAILED

        try:
            self._indexer.build(self._entry, self._store)
        except Exception as exc:  # 线程内异常不得冒泡到事件循环
            self._store.set_status(self._entry.id, STATUS_FAILED, str(exc))


class SettingsController(QObject):
    """设置页的数据与动作；QML 侧上下文名 `settingsCtl`。"""

    profilesChanged = Signal()
    projectsChanged = Signal()
    stylesChanged = Signal()
    modelsFetched = Signal(list)
    # profileId, 成功与否, 详情（耗时或错误原因）
    profileTested = Signal(str, bool, str)
    # 文案, 是否错误色
    messageChanged = Signal()

    def __init__(
        self,
        model: SettingsModel,
        base_dir: Path | None = None,
        style_store: StyleStore | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._profile_store = ProfileStore(base_dir=base_dir)
        self._project_store = ProjectStore(base_dir=base_dir)
        self._style_store = style_store or StyleStore(base_dir=base_dir)
        self._indexer = Indexer(base_dir=base_dir)
        self._message = ""
        self._message_error = False
        # 持有线程引用：QThread 被回收会导致进程崩溃
        self._threads: list[QThread] = []

    # ---------- 列表数据 ----------
    def _get_profiles(self) -> list[dict]:
        return [
            {
                "id": p.id,
                "name": p.name,
                "model": p.model,
                "baseUrl": p.base_url,
                "apiKey": p.api_key,  # 始终脱敏值
                "enabled": p.enabled,
            }
            for p in self._profile_store.list()
        ]

    def _get_projects(self) -> list[dict]:
        return [
            {
                "id": e.id,
                "name": e.name,
                "path": e.path,
                "status": e.index_status,
                "statusText": _STATUS_TEXT.get(e.index_status, e.index_status),
                "error": e.error,
            }
            for e in self._project_store.list()
        ]

    def _get_styles(self) -> list[dict]:
        return [
            {
                "id": r.key,
                "label": r.label,
                "instruction": r.instruction,
                "maxTokens": r.max_tokens,
                "builtin": r.builtin,
                "mode": r.mode,
                "description": r.description,
            }
            for r in self._style_store.records()
        ]

    profiles = Property("QVariantList", _get_profiles, notify=profilesChanged)
    projects = Property("QVariantList", _get_projects, notify=projectsChanged)
    styles = Property("QVariantList", _get_styles, notify=stylesChanged)

    def _get_message(self) -> str:
        return self._message

    def _get_message_error(self) -> bool:
        return self._message_error

    message = Property(str, _get_message, notify=messageChanged)
    messageError = Property(bool, _get_message_error, notify=messageChanged)

    def _emit(self, text: str, error: bool = False) -> None:
        self._message = text
        self._message_error = error
        self.messageChanged.emit()

    # ---------- 通用 ----------
    @Slot()
    def reload(self) -> None:
        """重新读取两个存储（列表可能与外部写入不一致时调用）。"""
        self.profilesChanged.emit()
        self.projectsChanged.emit()

    def notify(self, text: str, error: bool = False) -> None:
        """供 Python 侧向页面底部保存栏推一条文案（如保存失败的校验原因）。"""
        self._emit(text, error)

    @Slot(result=bool)
    def save(self) -> bool:
        """保存设置（委托 SettingsModel，含热键与预算校验）。"""
        if self._model.save():
            self._emit("已保存，重启后仍生效")
            return True
        return False

    # ---------- 模型配置 ----------
    @Slot(str, str, str, str, result=bool)
    def addProfile(self, name: str, base_url: str, api_key: str, model: str) -> bool:
        try:
            self._profile_store.add(
                name=name.strip(),
                provider="openai",
                base_url=base_url.strip(),
                api_key=api_key.strip(),
                model=model.strip(),
                temperature=1.0,
                max_tokens=6000,
                enabled=False,
            )
        except ValueError as exc:
            self._emit(str(exc), error=True)
            return False
        self._emit("已新增模型配置")
        self.profilesChanged.emit()
        return True

    @Slot(str, str, str, str, str, bool, result=bool)
    def updateProfile(
        self,
        profile_id: str,
        name: str,
        base_url: str,
        model: str,
        api_key: str,
        key_edited: bool,
    ) -> bool:
        """保存条目修改。key_edited 为 False 时不写回 api_key（掩码值不可还原）。"""
        fields = {
            "name": name.strip(),
            "base_url": base_url.strip(),
            "model": model.strip(),
        }
        if key_edited:
            fields["api_key"] = api_key.strip()
        if self._profile_store.update(profile_id, **fields) is None:
            self._emit("配置不存在，可能已被删除", error=True)
            return False
        self._emit("已保存修改")
        self.profilesChanged.emit()
        return True

    @Slot(str)
    def deleteProfile(self, profile_id: str) -> None:
        self._profile_store.delete(profile_id)
        self._emit("已删除模型配置")
        self.profilesChanged.emit()

    @Slot(str, bool)
    def setProfileEnabled(self, profile_id: str, enabled: bool) -> None:
        self._profile_store.set_enabled(profile_id, enabled)
        self.profilesChanged.emit()

    # ---------- 风格预设 ----------
    @Slot(str, str, int, result=bool)
    def addStyle(self, label: str, instruction: str, max_tokens: int) -> bool:
        """新增一条自定义风格预设。"""
        try:
            self._style_store.add(
                label=label.strip(),
                instruction=instruction,
                max_tokens=max_tokens,
            )
        except ValueError as exc:
            self._emit(str(exc), error=True)
            return False
        self._emit("已新增风格预设")
        self.stylesChanged.emit()
        return True

    @Slot(str, str, str, int, result=bool)
    def updateStyle(
        self, key: str, label: str, instruction: str, max_tokens: int
    ) -> bool:
        """保存风格预设修改。"""
        try:
            ok = self._style_store.update(
                key,
                label=label.strip(),
                instruction=instruction,
                max_tokens=max_tokens,
            )
        except ValueError as exc:
            self._emit(str(exc), error=True)
            return False
        if not ok:
            self._emit("预设不存在，可能已被删除", error=True)
            return False
        self._emit("已保存修改")
        self.stylesChanged.emit()
        return True

    @Slot(str)
    def deleteStyle(self, key: str) -> None:
        self._style_store.delete(key)
        self._emit("已删除风格预设")
        self.stylesChanged.emit()

    @Slot(str, result=str)
    def revealKey(self, profile_id: str) -> str:
        """取回明文 key（仅供界面「查看」按钮一次性展示）。"""
        return self._profile_store.reveal_key_by_id(profile_id)

    @Slot(str, str)
    def fetchModels(self, base_url: str, api_key: str) -> None:
        if not base_url.strip() or not api_key.strip():
            self._emit("请先填写 Base URL 与 API Key", error=True)
            return
        self._emit("正在获取模型列表…")
        # 显式透传超时：端点不通时由 ModelsFetchThread 内的 fetch_models 抛出
        # 「获取模型超时」并走 failed 信号，不会让「获取中…」一直停留。
        thread = ModelsFetchThread(base_url.strip(), api_key.strip(), self)
        thread.modelsReady.connect(self._on_models_ready)
        # 失败也要回传空列表：QML 依赖该信号退出「获取中…」状态
        thread.failed.connect(lambda msg: self._on_models_failed(msg))
        self._track(thread)
        thread.start()

    def _on_models_ready(self, models: list) -> None:
        self._emit(f"获取到 {len(models)} 个模型，请选择")
        self.modelsFetched.emit(models)

    def _on_models_failed(self, message: str) -> None:
        self._emit(message, error=True)
        self.modelsFetched.emit([])

    @Slot(str)
    def testProfile(self, profile_id: str) -> None:
        profile = self._profile_store.get(profile_id)
        if profile is None:
            self._emit("配置不存在，可能已被删除", error=True)
            return
        thread = _TestThread(
            profile.base_url,
            self._profile_store.reveal_key_by_id(profile_id),
            profile.model,
            self,
        )
        thread.succeeded.connect(
            lambda elapsed: self._on_test_result(profile_id, True, f"耗时 {elapsed}s")
        )
        thread.failed.connect(
            lambda msg: self._on_test_result(profile_id, False, msg)
        )
        self._track(thread)
        thread.start()

    def _on_test_result(self, profile_id: str, ok: bool, detail: str) -> None:
        self._emit(f"连通性测试{'成功' if ok else '失败'}{'，' + detail if detail else ''}", error=not ok)
        self.profileTested.emit(profile_id, ok, detail)

    # ---------- 项目索引 ----------
    @Slot(str, result=bool)
    def addProject(self, path: str) -> bool:
        from pathlib import Path

        text = path.strip()
        if not text:
            self._emit("请输入项目路径", error=True)
            return False
        if not Path(text).exists():
            self._emit("路径不存在", error=True)
            return False
        self._project_store.add(text)
        self._emit("已添加项目")
        self.projectsChanged.emit()
        return True

    @Slot(str)
    def deleteProject(self, entry_id: str) -> None:
        self._project_store.delete(entry_id)
        self._emit("已删除项目")
        self.projectsChanged.emit()

    @Slot(str)
    def buildIndex(self, entry_id: str) -> None:
        from context_pilot.projects.projects import STATUS_RUNNING

        entry = self._project_store.get(entry_id)
        if entry is None:
            self._emit("项目不存在，可能已被删除", error=True)
            return
        self._project_store.set_status(entry_id, STATUS_RUNNING)
        self.projectsChanged.emit()
        self._emit("正在创建索引…")

        thread = _IndexThread(self._indexer, entry, self._project_store, self)
        thread.finished.connect(self._on_index_done)
        self._track(thread)
        thread.start()

    def _on_index_done(self) -> None:
        self.projectsChanged.emit()
        entries = self._project_store.list()
        failed = next((e for e in entries if e.index_status == "failed"), None)
        if failed is not None:
            self._emit(f"索引失败：{failed.error}", error=True)
        else:
            self._emit("索引已完成")

    # ---------- 线程持有 ----------
    def _track(self, thread: QThread) -> None:
        self._threads.append(thread)
        thread.finished.connect(lambda: self._discard(thread))

    def _discard(self, thread: QThread) -> None:
        """线程结束后从持有列表移除。

        刻意**不**调用 deleteLater：QThread 的 delayed delete 若落在线程尚未完全
        停止的时刻，Qt 会直接 fatal abort（try/except 拦不住，且崩溃点在实际的
        下一次 processEvents，与真正出处相隔很远）。线程以 controller 为 parent，
        随 controller 销毁自然回收，生命周期更可预测。
        """
        if thread in self._threads:
            self._threads.remove(thread)

    @Slot()
    def shutdown(self) -> None:
        """放弃对后台线程的持有，回收交回 Qt 的父子关系。窗口关闭 / 退出前调用。

        刻意**不**在这里 wait 或 deleteLater：线程 finished 时 `_discard` 已经排过
        一次 delayed delete，若此时再触碰该对象，很可能作用在已被销毁的内存上
        ——C++ 层的 abort，try/except 拦不住。清掉 Python 侧的持有即可，剩余生命
        周期由 Qt 按 parent 关系处理。
        """
        self._threads.clear()
