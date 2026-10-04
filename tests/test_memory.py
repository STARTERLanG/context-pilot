"""项目记忆单测。存储隔离到 tmp_path，不触碰用户家目录。"""

import pytest

from context_pilot.memory.models import MemoryType
from context_pilot.memory.retriever import MemoryRetriever
from context_pilot.memory.store import MemoryStore, project_hash
from context_pilot.project.models import ProjectContext
from context_pilot.retrieval.base import Retriever


def _store(tmp_path) -> MemoryStore:
    return MemoryStore(tmp_path, base_dir=tmp_path / "memroot")


def test_add_and_list_roundtrip(tmp_path):
    store = _store(tmp_path)
    store.add("项目使用 FastAPI", MemoryType.PROJECT_FACT)

    memories = store.list()

    assert len(memories) == 1
    assert memories[0].content == "项目使用 FastAPI"
    assert memories[0].type is MemoryType.PROJECT_FACT


def test_add_empty_content_raises(tmp_path):
    with pytest.raises(ValueError):
        _store(tmp_path).add("   ")


def test_persists_across_store_instances(tmp_path):
    _store(tmp_path).add("退款逻辑独立于 OrderService")
    # 新实例重新打开同一库
    memories = MemoryStore(tmp_path, base_dir=tmp_path / "memroot").list()
    assert len(memories) == 1


def test_delete_removes_memory(tmp_path):
    store = _store(tmp_path)
    memory = store.add("临时结论")
    assert store.delete(memory.id) is True
    assert store.list() == []


def test_different_projects_use_different_db(tmp_path):
    assert project_hash(tmp_path / "a") != project_hash(tmp_path / "b")


def test_retriever_matches_memory_by_keyword(tmp_path):
    store = _store(tmp_path)
    store.add("OrderService 不得直接依赖 RefundService", MemoryType.ARCHITECTURE_DECISION)
    store.add("无关的记忆内容")

    project = ProjectContext(root=tmp_path.resolve())
    results = MemoryRetriever(store).search("修改 OrderService 逻辑", project)

    assert len(results) == 1
    assert results[0].type == "memory"
    assert "OrderService" in results[0].content


def test_retriever_returns_empty_for_pure_chinese_query(tmp_path):
    store = _store(tmp_path)
    store.add("项目使用 FastAPI")
    project = ProjectContext(root=tmp_path.resolve())
    assert MemoryRetriever(store).search("修一下订单接口", project) == []


def test_memory_retriever_satisfies_protocol(tmp_path):
    assert isinstance(MemoryRetriever(_store(tmp_path)), Retriever)
