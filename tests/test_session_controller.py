"""SessionController 单测（临时 HOME + 临时 data 目录，不碰用户真实数据）。

覆盖主页面「项目 / 模型」下拉的三件事：
- 候选：模型下拉只列「已生效」的配置，未生效的不出现；
- 选中：恰好一条生效时自动选中，多条生效时必须手动选，未选时 hasModelSelected
  为 False（界面据此禁用增强入口）；
- 立即生效：provider_target() / current_project_root 给出装配层重建管线所需的目标。
"""

import pytest
from PySide6.QtCore import QCoreApplication

from context_pilot.config import Config, GeneralConfig
from context_pilot.models.profiles import ProfileStore
from context_pilot.projects.projects import ProjectStore
from context_pilot.ui.session_controller import SessionController


@pytest.fixture(scope="module")
def qapp():
    return QCoreApplication.instance() or QCoreApplication([])


@pytest.fixture
def isolated_home(monkeypatch, tmp_path):
    """把「用户目录」重定向到临时目录（Windows 读 USERPROFILE，POSIX 读 HOME）。"""
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def stores(isolated_home, qapp):
    data = isolated_home / "data"
    data.mkdir(parents=True, exist_ok=True)
    return ProfileStore(base_dir=data), ProjectStore(base_dir=data), data


@pytest.fixture
def config(isolated_home):
    return Config(general=GeneralConfig(project_root=str(isolated_home / "repo")))


@pytest.fixture
def ctl(qapp, config, stores):
    _, _, data = stores
    return SessionController(config, base_dir=data)


@pytest.fixture
def empty_dir(isolated_home):
    data = isolated_home / "empty-data"
    data.mkdir(parents=True, exist_ok=True)
    return data


def _add_profile(profiles, name, model, key="sk-x", enabled=False):
    return profiles.add(
        name=name,
        provider="openai",
        base_url=f"https://{name}.test/v1",
        api_key=key,
        model=model,
        temperature=0.2,
        max_tokens=100,
        enabled=enabled,
    )


def _ids(items):
    return [item["id"] for item in items]


# ---------- 默认项 ----------
def test_projects_have_default_when_empty(ctl):
    projects = ctl.projects
    assert len(projects) == 1
    assert projects[0]["name"] == "无项目"
    assert projects[0]["isDefault"] is True
    assert ctl.currentProjectId == projects[0]["id"]
    assert ctl.currentProjectLabel == "无项目"
    assert ctl.has_project is False


def test_default_project_means_no_code_retrieval(ctl, config):
    """「无项目」默认选中时：current_project_root 为空，装配层据此跳过代码检索。"""
    assert ctl.current_project_root == ""
    assert ctl.has_project is False


def test_styles_default_and_selection(ctl):
    """模式候选列表齐全，默认结构化增强；选中后立即切换（会话级，不落盘）。"""
    assert [s["id"] for s in ctl.styles] == ["default", "basic", "professional", "planning"]
    assert ctl.current_style == "default"
    assert ctl.currentStyleLabel == "结构化增强"

    ctl.selectStyle("basic")
    assert ctl.current_style == "basic"
    assert ctl.currentStyleLabel == "基础优化"

    # 每种模式都带介绍文案（供聚焦展示）
    desc = {s["id"]: s["description"] for s in ctl.styles}
    assert desc["default"]
    assert desc["basic"]
    assert desc["professional"]
    assert desc["planning"]


def test_selecting_project_restores_root(empty_dir, qapp):
    """选中真实项目后才有项目根目录；「无项目」时根目录为空串。"""
    ctl = SessionController(Config(), base_dir=empty_dir)
    assert ctl.current_project_root == ""
    assert ctl.has_project is False


def test_no_candidates_without_enabled_profile(ctl):
    """没有生效配置时下拉为空，且提示去设置页勾选。"""
    assert ctl.models == []
    assert ctl.currentModelId == ""
    assert ctl.currentModelLabel == ""
    assert ctl.hasCandidates is False
    assert "设置页" in ctl.modelsHint


# ---------- 列表来源 ----------
def test_projects_list_includes_added_project(ctl, stores, isolated_home):
    _, projects, _ = stores
    entry = projects.add(str(isolated_home / "repo"))
    ctl.reload()

    assert entry.id in _ids(ctl.projects)
    assert ctl.projects[0]["id"] == "default"  # 默认项始终留在首位
    added = next(item for item in ctl.projects if item["id"] == entry.id)
    assert added["isDefault"] is False
    assert added["statusText"] == "未创建"
    assert added["detail"]  # 展示用的短路径


def test_models_only_include_enabled_profiles(ctl, stores):
    """未生效的配置不出现在下拉里；只有一条生效时自动选中。"""
    profiles, _, _ = stores
    disabled = _add_profile(profiles, "alpha", "model-a")
    enabled = _add_profile(profiles, "beta", "model-b", enabled=True)
    ctl.reload()

    assert _ids(ctl.models) == [enabled.id]
    assert disabled.id not in _ids(ctl.models)
    assert ctl.models[0] == {
        "id": enabled.id,
        "name": "model-b",
        "detail": "beta",
    }
    assert ctl.currentModelId == enabled.id
    assert ctl.currentModelLabel == "model-b"
    assert ctl.hasModelSelected is True


def test_multiple_enabled_requires_manual_selection(ctl, stores):
    """多条生效时不再自动挑一条：留空并由界面提示用户手动选择。"""
    profiles, _, _ = stores
    first = _add_profile(profiles, "alpha", "model-a", enabled=True)
    second = _add_profile(profiles, "beta", "model-b", enabled=True)
    ctl.reload()

    assert _ids(ctl.models) == [first.id, second.id]
    assert ctl.currentModelId == ""
    assert ctl.currentModelLabel == ""
    assert ctl.hasModelSelected is False
    assert "选择" in ctl.modelsHint

    ctl.selectModel(second.id)
    assert ctl.currentModelId == second.id
    assert ctl.currentModelLabel == "model-b"
    assert ctl.hasModelSelected is True


def test_selection_preserved_when_other_profile_enabled(ctl, stores):
    """新增一条生效配置不应清掉用户已选的增强目标。"""
    profiles, _, _ = stores
    first = _add_profile(profiles, "alpha", "model-a", enabled=True)
    ctl.reload()
    assert ctl.currentModelId == first.id  # 唯一生效 → 自动选中

    _add_profile(profiles, "beta", "model-b", enabled=True)
    ctl.reload()
    assert ctl.currentModelId == first.id
    assert ctl.hasModelSelected is True


def test_disabling_selected_profile_clears_selection(ctl, stores):
    """选中的配置被停用后必须清空，不能继续指向一个已不可用的目标。"""
    profiles, _, _ = stores
    first = _add_profile(profiles, "alpha", "model-a", enabled=True)
    ctl.reload()
    assert ctl.currentModelId == first.id

    profiles.set_enabled(first.id, False)
    ctl.reload()
    assert ctl.models == []
    assert ctl.currentModelId == ""
    assert ctl.hasCandidates is False
    assert ctl.provider_target() is None


# ---------- 选择：会话内保持 + 立即生效 ----------
def test_select_project_changes_root(ctl, stores, isolated_home):
    _, projects, _ = stores
    entry = projects.add(str(isolated_home / "another-repo"))
    ctl.reload()

    assert ctl.current_project_root == ""  # 未选中真实项目前为空
    ctl.selectProject(entry.id)
    assert ctl.currentProjectId == entry.id
    assert ctl.current_project_root == entry.path
    assert ctl.has_project is True


def test_selection_survives_reload(ctl, stores, isolated_home):
    """会话内持久：设置页改动同一份数据后刷新，已选项目仍在。"""
    _, projects, _ = stores
    entry = projects.add(str(isolated_home / "repo"))
    ctl.reload()
    ctl.selectProject(entry.id)

    projects.add(str(isolated_home / "other"))  # 列表变动
    ctl.reload()
    assert ctl.currentProjectId == entry.id


def test_deleted_selection_falls_back_to_default(ctl, stores, isolated_home):
    _, projects, _ = stores
    entry = projects.add(str(isolated_home / "repo"))
    ctl.reload()
    ctl.selectProject(entry.id)

    projects.delete(entry.id)
    ctl.reload()
    assert ctl.currentProjectId == "default"
    assert ctl.currentProjectLabel == "无项目"
    assert ctl.has_project is False


def test_selection_emits_signal(ctl, stores, isolated_home, qapp):
    profiles, projects, _ = stores
    entry = projects.add(str(isolated_home / "repo"))
    profile = _add_profile(profiles, "beta", "model-b", enabled=True)
    ctl.reload()

    seen = []
    ctl.selectionChanged.connect(lambda: seen.append(True))
    ctl.selectProject(entry.id)
    ctl.selectModel(profile.id)
    assert len(seen) == 2


def test_auto_selection_emits_signal(stores, config, qapp):
    """唯一生效配置被自动选中时也要通知装配层，否则界面与调用目标不一致。"""
    profiles, _, data = stores
    _add_profile(profiles, "beta", "model-b", enabled=True)
    ctl = SessionController(config, base_dir=data)

    seen = []
    ctl.selectionChanged.connect(lambda: seen.append(True))
    ctl.reload()
    # 构造函数已自动选中，reload 不再变化 → 不发信号
    assert seen == []

    profiles.set_enabled(profiles.list()[0].id, False)
    ctl.reload()
    assert ctl.currentModelId == ""
    assert len(seen) == 1


# ---------- provider 目标 ----------
def test_provider_target_none_without_selection(ctl):
    """没有生效配置 → 没有目标，装配层据此让调用明确失败而不是猜。"""
    assert ctl.provider_target() is None


def test_provider_target_follows_selected_model(ctl, stores):
    profiles, _, _ = stores
    chosen = _add_profile(profiles, "beta", "model-b", key="sk-b", enabled=True)
    ctl.reload()
    ctl.selectModel(chosen.id)

    assert ctl.provider_target() == {
        "base_url": "https://beta.test/v1",
        "api_key": "sk-b",  # 明文只在 Python 侧出现，不外泄到 QML
        "model": "model-b",
        "temperature": 0.2,
    }


def test_provider_target_none_when_key_missing(ctl, stores):
    """没有可用 Key 时不编造目标。"""
    profiles, _, _ = stores
    empty = _add_profile(profiles, "nokey", "model-b", key="", enabled=True)
    ctl.reload()
    ctl.selectModel(empty.id)
    assert ctl.provider_target() is None


# ---------- 空数据 ----------
def test_models_empty_without_any_source(empty_dir, qapp):
    """没有任何已生效配置时，列表为空但不崩，标签为空串。"""
    ctl = SessionController(Config(), base_dir=empty_dir)
    assert ctl.models == []
    assert ctl.currentModelId == ""
    assert ctl.currentModelLabel == ""
    assert ctl.hasCandidates is False
    # 没有可用目标就不增强：不静默回落到离线桩
    assert ctl.hasModelSelected is False


def test_candidates_come_from_enabled_profiles_only(stores, qapp):
    """只要勾了模型就应列出并要求选择，不再有任何配置开关能把它藏起来。

    回归：从前用 config.llm.provider 判断，而设置页没有切换入口，该字段
    永远是默认值 stub，导致勾选生效的模型在下拉里根本看不到。
    """
    profiles, _, data = stores
    first = _add_profile(profiles, "alpha", "model-a", enabled=True)
    second = _add_profile(profiles, "beta", "model-b", enabled=True)

    ctl = SessionController(Config(), base_dir=data)
    assert _ids(ctl.models) == [first.id, second.id]
    assert ctl.hasCandidates is True
    assert ctl.currentModelId == ""  # 多条生效：等用户选
    assert ctl.hasModelSelected is False

    ctl.selectModel(second.id)
    assert ctl.provider_target()["model"] == "model-b"


# ---------- 增强目标跨启动保留 ----------
def test_selected_model_is_remembered_across_restarts(stores, config, qapp):
    """手动选定的增强目标重启后仍在：多条生效时不必每次重新选一遍。"""
    profiles, _, data = stores
    first = _add_profile(profiles, "alpha", "model-a", enabled=True)
    second = _add_profile(profiles, "beta", "model-b", enabled=True)

    ctl = SessionController(config, base_dir=data)
    ctl.selectModel(second.id)

    # 新实例 = 下次启动
    again = SessionController(config, base_dir=data)
    assert again.currentModelId == second.id
    assert again.currentModelLabel == "model-b"
    assert again.hasModelSelected is True
    assert again.provider_target()["model"] == "model-b"
    assert first.id != second.id


def test_remembered_model_ignored_when_no_longer_enabled(stores, config, qapp):
    """记住的目标被停用后不能沿用：回落规则优先于记忆。"""
    profiles, _, data = stores
    first = _add_profile(profiles, "alpha", "model-a", enabled=True)
    second = _add_profile(profiles, "beta", "model-b", enabled=True)

    ctl = SessionController(config, base_dir=data)
    ctl.selectModel(second.id)
    profiles.set_enabled(second.id, False)

    again = SessionController(config, base_dir=data)
    # 只剩一条生效 → 自动选中它，而不是硬指向已停用的那条
    assert again.currentModelId == first.id
    assert again.provider_target()["model"] == "model-a"


def test_remembered_model_ignored_when_deleted(stores, config, qapp):
    """记住的目标被删除后不悬空：没有候选就留空。"""
    profiles, _, data = stores
    only = _add_profile(profiles, "alpha", "model-a", enabled=True)
    ctl = SessionController(config, base_dir=data)
    ctl.selectModel(only.id)

    profiles.delete(only.id)
    again = SessionController(config, base_dir=data)
    assert again.currentModelId == ""
    assert again.hasModelSelected is False
    assert again.provider_target() is None


def test_auto_selected_model_is_remembered(stores, config, qapp):
    """自动选中的也记住：恢复的应是「这次实际在用的目标」。"""
    profiles, _, data = stores
    only = _add_profile(profiles, "alpha", "model-a", enabled=True)
    SessionController(config, base_dir=data)  # 唯一生效 → 自动选中并记住

    # 之后又启用第二条：上次实际用的是 model-a，应继续沿用它
    _add_profile(profiles, "beta", "model-b", enabled=True)
    again = SessionController(config, base_dir=data)
    assert again.currentModelId == only.id


def test_select_model_rejects_unknown_id(ctl, stores):
    """未生效/已删除的配置不能成为增强目标（下拉之外的调用也拦得住）。"""
    profiles, _, _ = stores
    enabled = _add_profile(profiles, "beta", "model-b", enabled=True)
    disabled = _add_profile(profiles, "alpha", "model-a", enabled=False)
    ctl.reload()

    ctl.selectModel(disabled.id)
    assert ctl.currentModelId == enabled.id  # 唯一生效项保持不变

    ctl.selectModel("not-exist")
    assert ctl.currentModelId == enabled.id
