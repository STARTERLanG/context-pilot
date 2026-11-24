"""记忆写入链路单测：抽取 → 查重 → 用户确认 → 入库。

重点验证这条链路真正闭环（此前 extract() 只有测试调用、add() 无生产点）：
候选必须经确认才落库，且库按项目隔离、切换项目时旧候选失效。
"""

from context_pilot.memory.retriever import MemoryRetriever
from context_pilot.memory.store import MemoryStore
from context_pilot.project.models import ProjectContext
from context_pilot.ui.memory_controller import MemoryController

_TEXT = "这个项目必须使用 FastAPI。不要直连数据库。上次决定用 Redis 做缓存。"


def _controller(tmp_path, root=None):
    return MemoryController(str(root or tmp_path), base_dir=tmp_path / "memroot")


def test_collect_extracts_candidates_with_labels(tmp_path):
    ctl = _controller(tmp_path)

    count = ctl.collect(_TEXT)

    assert count == len(ctl.candidates) == 3
    types = {row["type"] for row in ctl.candidates}
    assert "架构决策" in types  # 必须
    assert "用户偏好" in types  # 不要
    assert "历史结论" in types  # 决定
    assert all(row["selected"] for row in ctl.candidates)


def test_collect_without_project_returns_zero(tmp_path):
    ctl = MemoryController("", base_dir=tmp_path / "memroot")

    assert ctl.collect(_TEXT) == 0
    assert ctl.candidates == []


def test_candidates_not_written_before_confirm(tmp_path):
    ctl = _controller(tmp_path)
    ctl.collect(_TEXT)

    store = MemoryStore(tmp_path, base_dir=tmp_path / "memroot")
    assert store.list() == []


def test_confirm_writes_selected_only(tmp_path):
    ctl = _controller(tmp_path)
    ctl.collect(_TEXT)
    saved = []
    ctl.saved.connect(lambda n: saved.append(n))

    # 只勾选第 0、2 条
    ctl.confirm([0, 2])

    store = MemoryStore(tmp_path, base_dir=tmp_path / "memroot")
    rows = store.list()
    assert len(rows) == 2
    assert saved == [2]
    assert ctl.candidates == []  # 入库后候选清空


def test_confirm_all_then_retrievable(tmp_path):
    """端到端：确认入库后，检索器能把它作为上下文项取回。"""
    ctl = _controller(tmp_path)
    ctl.collect("必须使用 FastAPI，不要直连数据库。")
    ctl.confirm(list(range(len(ctl.candidates))))

    store = MemoryStore(tmp_path, base_dir=tmp_path / "memroot")
    results = MemoryRetriever(store).search("要不要直连数据库", ProjectContext(root=tmp_path))
    assert results
    assert any("数据库" in item.content for item in results)


def test_conflict_detection_marks_existing_memory(tmp_path):
    base = tmp_path / "memroot"
    MemoryStore(tmp_path, base_dir=base).add("必须使用 FastAPI 框架")
    ctl = _controller(tmp_path)

    ctl.collect("必须使用 FastAPI 框架")

    assert ctl.candidates
    assert ctl.candidates[0]["conflicts"]


def test_toggle_updates_selection(tmp_path):
    ctl = _controller(tmp_path)
    ctl.collect(_TEXT)

    assert ctl.toggle(0) is False
    assert ctl.candidates[0]["selected"] is False
    assert ctl.toggle(0) is True


def test_set_project_root_clears_candidates(tmp_path):
    ctl = _controller(tmp_path)
    ctl.collect(_TEXT)
    assert ctl.candidates

    ctl.set_project_root(str(tmp_path / "another"))

    assert ctl.project_root == str(tmp_path / "another")
    assert ctl.candidates == []


def test_new_collect_replaces_previous_candidates(tmp_path):
    ctl = _controller(tmp_path)
    ctl.collect(_TEXT)
    first = [row["content"] for row in ctl.candidates]

    ctl.collect("这是一段没有任何决策关键词的普通句子。")

    assert ctl.candidates == [] or [row["content"] for row in ctl.candidates] != first


def test_confirm_out_of_range_index_ignored(tmp_path):
    ctl = _controller(tmp_path)
    ctl.collect(_TEXT)
    saved = []
    ctl.saved.connect(lambda n: saved.append(n))

    ctl.confirm([99])

    assert saved == []
    assert MemoryStore(tmp_path, base_dir=tmp_path / "memroot").list() == []
