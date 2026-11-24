"""记忆管理控制器单测：项目/全局两类隔离、编辑、删除、刷新一致性。"""

from context_pilot.memory.models import MemoryType
from context_pilot.memory.retriever import MemoryRetriever
from context_pilot.memory.store import MemoryStore
from context_pilot.project.models import ProjectContext
from context_pilot.projects.projects import ProjectStore
from context_pilot.ui.memory_manage_controller import MemoryManageController


def _ctl(tmp_path, root=None):
    return MemoryManageController(str(root or tmp_path), base_dir=tmp_path / "memroot")


def test_two_scopes_are_isolated(tmp_path):
    ctl = _ctl(tmp_path)
    ctl.add("project", "仅本项目生效", "项目事实")
    ctl.add("global", "对所有项目生效", "用户偏好")

    assert len(ctl.projectMemories) == 1
    assert len(ctl.globalMemories) == 1
    assert ctl.projectMemories[0]["content"] == "仅本项目生效"
    assert ctl.globalMemories[0]["content"] == "对所有项目生效"
    assert ctl.projectMemories[0]["scope"] == "project"
    assert ctl.globalMemories[0]["scope"] == "global"


def test_global_store_not_under_project_hash(tmp_path):
    """全局库位置固定，不能落在某个项目的哈希目录里。"""
    project_store = MemoryStore(tmp_path, base_dir=tmp_path / "memroot")
    global_store = MemoryStore("", base_dir=tmp_path / "memroot", scope="global")
    assert project_store.path != global_store.path
    assert "_global" in str(global_store.path)


def test_update_content_and_type(tmp_path):
    ctl = _ctl(tmp_path)
    ctl.add("project", "原始内容", "项目事实")
    memory_id = ctl.projectMemories[0]["id"]

    ctl.update("project", memory_id, "改成架构决策", "架构决策")

    assert ctl.projectMemories[0]["content"] == "改成架构决策"
    assert ctl.projectMemories[0]["type"] == "架构决策"


def test_delete_removes_from_correct_scope(tmp_path):
    ctl = _ctl(tmp_path)
    ctl.add("project", "项目记忆", "项目事实")
    ctl.add("global", "全局记忆", "用户偏好")

    ctl.delete("project", ctl.projectMemories[0]["id"])

    assert ctl.projectMemories == []
    assert len(ctl.globalMemories) == 1


def test_switch_project_keeps_global_drops_project_view(tmp_path):
    ctl = _ctl(tmp_path, tmp_path / "a")
    ctl.add("project", "A 项目记忆", "项目事实")
    ctl.add("global", "通用偏好", "用户偏好")

    ctl.set_project_root(str(tmp_path / "b"))

    assert ctl.projectMemories == []
    assert len(ctl.globalMemories) == 1

    ctl.set_project_root(str(tmp_path / "a"))
    assert ctl.projectMemories[0]["content"] == "A 项目记忆"


def test_project_dropdown_filters_by_selected_project(tmp_path):
    """加项目下拉后：只展示所选那一个项目的记忆，不混合所有项目。"""
    memroot = tmp_path / "memroot"
    pa = tmp_path / "alpha"
    pb = tmp_path / "beta"
    pa.mkdir()
    pb.mkdir()
    projects = ProjectStore(base_dir=memroot)
    projects.add(str(pa))
    eb = projects.add(str(pb))

    # 各自写一条项目记忆（绕过控制器，直接对各自的库写入）
    MemoryStore(pa, base_dir=memroot).add("只属于 Alpha", MemoryType.PROJECT_FACT)
    MemoryStore(pb, base_dir=memroot).add("只属于 Beta", MemoryType.ARCHITECTURE_DECISION)
    MemoryStore("", base_dir=memroot, scope="global").add("通用约定", MemoryType.USER_PREFERENCE)

    ctl = MemoryManageController(str(pa), base_dir=memroot)

    assert "alpha" in ctl.projects
    assert "beta" in ctl.projects
    assert "无项目" in ctl.projects
    assert any(m["content"] == "只属于 Alpha" for m in ctl.projectMemories)

    # 切到 Beta：项目记忆只剩 Beta，全局记忆不受影响
    ctl.selectProjectByName(eb.name)
    assert [m["content"] for m in ctl.projectMemories] == ["只属于 Beta"]
    assert [m["content"] for m in ctl.globalMemories] == ["通用约定"]

    # 写到项目记忆时，落在当前选中的项目库里，而非主窗口最初的项目
    ctl.add("project", "新增到 Beta", "项目事实")
    assert any(m["content"] == "新增到 Beta" for m in ctl.projectMemories)
    assert any(
        m.content == "新增到 Beta" for m in MemoryStore(pb, base_dir=memroot).list()
    )
    assert all(
        m.content != "新增到 Beta" for m in MemoryStore(pa, base_dir=memroot).list()
    )


def test_manual_project_selection_not_overridden_by_main_window(tmp_path):
    """设置页手动选项目后，主窗口切项目不再覆盖该选择。"""
    memroot = tmp_path / "memroot"
    pa = tmp_path / "alpha"
    pb = tmp_path / "beta"
    pa.mkdir()
    pb.mkdir()
    projects = ProjectStore(base_dir=memroot)
    projects.add(str(pa))
    projects.add(str(pb))

    ctl = MemoryManageController(str(pa), base_dir=memroot)
    ctl.selectProjectByName("beta")

    ctl.set_project_root(str(pb))
    # 主窗口同步路径与手动选中一致时也不改；换成第三个项目仍应保持手动选择
    pc = tmp_path / "gamma"
    pc.mkdir()
    projects.add(str(pc))
    ctl.set_project_root(str(pc))
    assert ctl.selectedProject == "beta"
    assert ctl._active_project_path() == str(pb)


def test_retriever_recalls_both_scopes(tmp_path):
    ctl = _ctl(tmp_path)
    ctl.add("project", "不要直连数据库", "架构决策")
    ctl.add("global", "所有项目都用中文注释", "用户偏好")

    project_store = MemoryStore(tmp_path, base_dir=tmp_path / "memroot")
    global_store = MemoryStore("", base_dir=tmp_path / "memroot", scope="global")
    results = MemoryRetriever(project_store, global_store=global_store).search(
        "要不要直连数据库", ProjectContext(root=tmp_path)
    )
    assert any("数据库" in r.content for r in results)

    results = MemoryRetriever(project_store, global_store=global_store).search(
        "中文注释", ProjectContext(root=tmp_path)
    )
    assert any("中文" in r.content for r in results)
    assert any(r.source.endswith("/global") for r in results)


def test_empty_content_rejected(tmp_path):
    ctl = _ctl(tmp_path)
    ctl.add("project", "   ", "项目事实")
    assert ctl.projectMemories == []
    assert "不能为空" in ctl.error


def test_edit_and_delete_reflect_on_disk(tmp_path):
    """编辑/删除后重新构造控制器，展示结果与磁盘一致。"""
    ctl = _ctl(tmp_path)
    ctl.add("global", "旧内容", "项目事实")
    memory_id = ctl.globalMemories[0]["id"]
    ctl.update("global", memory_id, "新内容", "用户偏好")
    assert _ctl(tmp_path).globalMemories[0]["content"] == "新内容"

    ctl.delete("global", memory_id)
    assert _ctl(tmp_path).globalMemories == []


def test_legacy_project_scope_written_by_old_add(tmp_path):
    """旧 add() 仍默认 project scope，兼容既有调用。"""
    store = MemoryStore(tmp_path, base_dir=tmp_path / "memroot")
    memory = store.add("项目使用 FastAPI", MemoryType.PROJECT_FACT)
    assert memory.scope == "project"
