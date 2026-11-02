"""主页面顶行的「项目 / 模型」选择：会话级选中态 + 立即生效。

与 SettingsController 的分工：
- 设置页负责**持久化**的数据（模型配置、项目索引的增删改）——settings_controller.py；
- 本控制器只读这些已持久化的数据，整理成 QML 可直接渲染的候选列表。

模型选择有两层语义，不能混：
- **生效**（设置页的勾选，可多条同时生效）表示「这条配置允许被使用」；
- **增强目标**（本控制器的 currentModelId）表示「这一次增强用哪一条」。
候选列表只包含已生效的配置；恰好只有一条时自动选中，两条及以上必须由用户
手动选——没有选中项时 hasModelSelected 为 False，界面据此禁用增强入口。

增强目标**跨启动保留**：用户明确选过的那一条写入 profiles.db 的 app_state，
下次启动若它仍处于「已生效」，就直接沿用。多条生效是常态，每次都重新选一遍
属于纯粹的重复劳动；但存储值只作参考——指向的配置被停用或删除时照样按下面的
回落规则处理，绝不会因此调到一个不可用的目标。项目选择仍只活在会话里。

选中变化发 selectionChanged，装配层（app.py）据此重建 Pipeline 与 Provider，
下一次增强即按新选择执行。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import Property, QObject, Signal, Slot

from context_pilot.config import Config
from context_pilot.models.profiles import SELECTED_MODEL_KEY, ProfileStore
from context_pilot.models.styles import StyleStore
from context_pilot.projects.projects import ProjectStore

# 默认项目：未添加任何项目（或当前配置根目录不在项目库里）时的兜底选项。
# 「无项目」语义：不针对特定项目代码库，仅优化原始表述，不检索项目代码。
DEFAULT_PROJECT_ID = "default"
# 默认输出风格：结构化增强（与 EnhanceOptions.style 默认值一致）
DEFAULT_STYLE = "default"

_INDEX_STATUS_TEXT = {
    "pending": "未创建",
    "running": "创建中",
    "done": "已完成",
    "failed": "失败",
}


class SessionController(QObject):
    """主页面顶行两个下拉的数据源与选中状态；QML 侧上下文名 `sessionCtl`。"""

    projectsChanged = Signal()
    projectsSelectionChanged = Signal()
    modelsChanged = Signal()
    # 任一项选中变化都会触发（装配层据此重建管线）
    selectionChanged = Signal()
    styleChanged = Signal()
    stylesChanged = Signal()

    def __init__(
        self,
        config: Config,
        base_dir: Path | None = None,
        style_store: StyleStore | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._profile_store = ProfileStore(base_dir=base_dir)
        self._project_store = ProjectStore(base_dir=base_dir)
        self._style_store = style_store or StyleStore(base_dir=base_dir)
        self._projects: list[dict] = []
        self._models: list[dict] = []
        self._project_id = DEFAULT_PROJECT_ID
        self._model_id = ""
        # 上次明确选定的增强目标（跨启动）。只是「候选参考值」：是否真的可用
        # 由 _reload_models 对着已生效列表校验，不可用就按回落规则重选。
        self._saved_model_id = self._profile_store.get_state(SELECTED_MODEL_KEY)
        # 输出风格选中态（会话级，不落盘）：默认结构化增强
        self._style = DEFAULT_STYLE
        self.reload()

    # ---------- 配置同步 ----------
    def set_config(self, config: Config) -> None:
        """设置保存后同步新配置（项目根目录可能变了）。"""
        self._config = config
        self.reload()

    @property
    def _has_candidates(self) -> bool:
        """是否存在任何已生效的模型配置。

        这是「要不要选模型」的唯一依据。从前用 config.llm.provider 判断，
        而设置页没有切换 provider 的入口，该字段会永远停在默认值 stub，
        导致勾选了模型也列不出来。
        """
        return bool(self._models)

    # ---------- 列表 ----------
    def _get_projects(self) -> list[dict]:
        return self._projects

    def _get_models(self) -> list[dict]:
        return self._models

    def _get_styles(self) -> list[dict]:
        return [
            {
                "id": s.key,
                "name": s.label,
                "detail": f"≈{s.max_tokens} tokens",
                "description": s.description,
            }
            for s in self._style_store.list()
        ]

    def _get_current_style(self) -> str:
        return self._style

    def _get_current_project_id(self) -> str:
        return self._project_id

    def _get_current_model_id(self) -> str:
        return self._model_id

    def _get_has_model_selected(self) -> bool:
        """本次增强是否具备明确的调用目标。

        没有目标就不增强：宁可按钮置灰并提示去设置页勾选，也不要静默回落到
        离线桩（结果只是把原文抄回来，用户会以为模型坏了）。
        """
        return bool(self._model_id)

    def _get_has_candidates(self) -> bool:
        """是否存在已生效的配置（供启动提示区分「没配置」与「配置了没选」）。"""
        return bool(self._models)

    def _get_models_hint(self) -> str:
        """模型下拉的提示文案：未选目标 / 无可用配置时给出明确下一步。"""
        if not self._models:
            return "设置页未勾选已生效模型"
        if not self._model_id:
            return "请选择增强模型"
        return ""

    def _get_current_project_label(self) -> str:
        return self._label(self._projects, self._project_id)

    def _get_current_model_label(self) -> str:
        return self._label(self._models, self._model_id)

    def _get_current_style_label(self) -> str:
        return self._label(self._get_styles(), self._style)

    projects = Property("QVariantList", _get_projects, notify=projectsChanged)
    models = Property("QVariantList", _get_models, notify=modelsChanged)
    styles = Property("QVariantList", _get_styles, notify=stylesChanged)
    currentProjectId = Property(str, _get_current_project_id, notify=projectsSelectionChanged)
    currentModelId = Property(str, _get_current_model_id, notify=modelsChanged)
    currentStyle = Property(str, _get_current_style, notify=styleChanged)
    # 选中项的展示名：下拉框收起态要显示它（列表本身不含「谁是选中」的可绑信息）
    currentProjectLabel = Property(
        str, _get_current_project_label, notify=projectsSelectionChanged
    )
    currentModelLabel = Property(str, _get_current_model_label, notify=modelsChanged)
    currentStyleLabel = Property(str, _get_current_style_label, notify=styleChanged)
    # 是否已选定增强目标：未选时增强入口应禁用（增强必须由用户明确指定模型）
    hasModelSelected = Property(bool, _get_has_model_selected, notify=modelsChanged)
    hasCandidates = Property(bool, _get_has_candidates, notify=modelsChanged)
    modelsHint = Property(str, _get_models_hint, notify=modelsChanged)

    @staticmethod
    def _label(items: list[dict], item_id: str) -> str:
        for item in items:
            if item.get("id") == item_id:
                return str(item.get("name", ""))
        # 兜底：选中项已从库中删除时显示名称，避免下拉框空着让人以为没选
        return ""

    # ---------- 选择 ----------
    @Slot(str)
    def selectProject(self, entry_id: str) -> None:
        self._project_id = entry_id or DEFAULT_PROJECT_ID
        self.projectsSelectionChanged.emit()
        self.selectionChanged.emit()

    @Slot(str)
    def selectModel(self, option_id: str) -> None:
        # 只接受候选列表内的 id：未生效/已删除的配置不能成为增强目标
        if option_id not in {item["id"] for item in self._models}:
            return
        self._model_id = option_id
        self._remember_model(option_id)
        self.modelsChanged.emit()
        self.selectionChanged.emit()

    @Slot(str)
    def selectStyle(self, style: str) -> None:
        if not style:
            return
        self._style = style
        self.styleChanged.emit()

    @Slot()
    def refreshStyles(self) -> None:
        """风格预设增删改后刷新下拉列表（并处理选中项被删除的回落）。"""
        keys = {s.key for s in self._style_store.list()}
        if self._style not in keys:
            self._style = DEFAULT_STYLE
            self.styleChanged.emit()
        self.stylesChanged.emit()

    @Slot()
    def reload(self) -> None:
        """重读两个库；选中项若仍可用则保留，否则按 _reload_models 的规则回落。"""
        self._reload_projects()
        self._reload_models()

    # ---------- 供 Python 装配层读取 ----------
    @property
    def has_project(self) -> bool:
        """当前是否选中了某个真实项目代码库（「无项目」时为 False）。"""
        return self._project_id != DEFAULT_PROJECT_ID

    @property
    def current_style(self) -> str:
        """当前选中的输出风格 key（供装配层构建 EnhanceOptions）。"""
        return self._style

    @property
    def style_store(self) -> StyleStore:
        """风格预设存储（供装配层与设置页共享同一份自定义预设）。"""
        return self._style_store

    def style_objects(self) -> list:
        """当前全部风格预设（OutputStyle 列表，供装配层构建 Pipeline）。"""
        return self._style_store.list()

    @property
    def current_project_root(self) -> str:
        """当前选中项目对应的根目录字符串。

        「无项目」时返回空串，装配层据此跳过项目扫描与代码检索。
        """
        if self._project_id == DEFAULT_PROJECT_ID:
            return ""
        for item in self._projects:
            if item.get("id") == self._project_id:
                path = str(item.get("path") or "")
                return path or self._default_root()
        return self._default_root()

    def provider_target(self) -> dict | None:
        """当前选中模型对应的调用目标；None 表示未选中可用模型。

        返回 dict(base_url, api_key, model, temperature)。明文 key 只在这里以
        Python 返回值形式交给装配层，**不作为 QML 属性暴露**。
        """
        if not self._model_id:
            return None
        profile = self._profile_store.get(self._model_id)
        if profile is None:
            return None
        key = self._profile_store.reveal_key_by_id(self._model_id)
        if not key or not profile.base_url:
            return None
        return {
            "base_url": profile.base_url,
            "api_key": key,
            "model": profile.model,
            "temperature": profile.temperature,
        }

    # ---------- 内部：项目列表 ----------
    def _default_root(self) -> str:
        return self._config.general.project_root or str(Path.cwd())

    def _reload_projects(self) -> None:
        items: list[dict] = [
            {
                "id": DEFAULT_PROJECT_ID,
                # 未添加任何项目时的唯一选项；表示不针对特定项目，仅优化原始表述
                "name": "无项目",
                "path": "",
                "detail": "仅优化表述",
                "isDefault": True,
            }
        ]
        for entry in self._project_store.list():
            items.append(
                {
                    "id": entry.id,
                    "name": entry.name or _short_path(entry.path),
                    "path": entry.path,
                    "detail": _short_path(entry.path),
                    "status": entry.index_status,
                    "statusText": _INDEX_STATUS_TEXT.get(entry.index_status, ""),
                    "isDefault": False,
                }
            )
        self._projects = items

        known = {item["id"] for item in items}
        if self._project_id not in known:
            # 选中的项目被删了：回到默认项，而不是悬着一个不存在的 id
            self._project_id = DEFAULT_PROJECT_ID
        self.projectsChanged.emit()
        self.projectsSelectionChanged.emit()

    # ---------- 内部：模型列表 ----------
    def _reload_models(self) -> None:
        """候选 = 已生效的模型配置（未生效的不出现在下拉里）。

        选中规则（按优先级）：
        - 当前选项仍在候选里 → 保持（会话内不因刷新丢失）；
        - 上次明确选过的那条仍在候选里 → 恢复（跨启动记住用户的选择）；
        - 候选恰好只有一条 → 自动选中；
        - 其余情况留空，由用户手动选择（多条生效时必须明确指定用哪条）。
        """
        enabled = self._profile_store.list_enabled()
        self._models = [
            {
                "id": p.id,
                "name": p.model,
                "detail": p.name,
            }
            for p in enabled
        ]

        known = {item["id"] for item in self._models}
        previous = self._model_id
        if self._model_id not in known:
            if self._saved_model_id in known:
                self._model_id = self._saved_model_id
            else:
                self._model_id = self._models[0]["id"] if len(self._models) == 1 else ""
        # 自动选中的也一并记住：下次启动恢复的应是「这次实际在用的目标」，
        # 而不是「只有手动点过的才算数」。
        if self._model_id:
            self._remember_model(self._model_id)
        self.modelsChanged.emit()
        # 自动选中/回落也是一次选择变化：装配层必须按新目标重建管线，
        # 否则界面显示的模型与真正调用的模型会不一致
        if self._model_id != previous:
            self.selectionChanged.emit()

    def _remember_model(self, option_id: str) -> None:
        """记住用户明确选定的增强目标，供下次启动恢复。

        写失败不影响本次选择：这是「下次省一步」的便利，不是功能前提，
        故只吞落盘相关异常（磁盘满 / 库被占用），不掩盖其它问题。
        """
        if option_id == self._saved_model_id:
            return
        self._saved_model_id = option_id
        try:
            self._profile_store.set_state(SELECTED_MODEL_KEY, option_id)
        except (OSError, sqlite3.Error):
            pass


def _short_path(path: str) -> str:
    """把绝对路径压成 parent/base 两级，便于在下拉里展示。"""
    p = Path(path)
    parts = p.parts
    if len(parts) <= 2:
        return str(p)
    return str(Path(*parts[-2:]))
