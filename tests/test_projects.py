"""项目条目存储与索引单测。"""

from pathlib import Path

from context_pilot.projects.indexer import Indexer
from context_pilot.projects.projects import (
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_PENDING,
    ProjectStore,
)


def _store(tmp_path):
    return ProjectStore(base_dir=tmp_path)


def test_add_list_and_duplicate_path(tmp_path):
    store = _store(tmp_path)
    a = store.add(str(tmp_path / "proj"))
    b = store.add(str(tmp_path / "proj"))
    assert a.id == b.id  # 重复路径返回既有记录
    assert len(store.list()) == 1


def test_add_resolves_and_names(tmp_path):
    store = _store(tmp_path)
    entry = store.add(str(tmp_path))
    assert Path(entry.path).is_absolute()
    assert entry.index_status == STATUS_PENDING
    assert entry.name  # 非空


def test_delete(tmp_path):
    store = _store(tmp_path)
    entry = store.add(str(tmp_path))
    assert store.delete(entry.id) is True
    assert store.get(entry.id) is None


def test_index_success(tmp_path):
    store = _store(tmp_path)
    project = tmp_path / "app"
    project.mkdir()
    (project / "main.py").write_text("def main(): pass\n", encoding="utf-8")
    (project / "node_modules").mkdir()
    (project / "node_modules" / "x.js").write_text("x", encoding="utf-8")

    entry = store.add(str(project))
    result = Indexer(base_dir=tmp_path).build(entry, store)

    assert result.error == ""
    assert store.get(entry.id).index_status == STATUS_DONE
    assert result.file_count == 1  # node_modules 被忽略


def test_index_missing_path_fails(tmp_path):
    store = _store(tmp_path)
    entry = store.add(str(tmp_path / "nope"))
    result = Indexer(base_dir=tmp_path).build(entry, store)

    assert result.error  # 可读错误
    assert store.get(entry.id).index_status == STATUS_FAILED


def test_index_file_not_dir_fails(tmp_path):
    store = _store(tmp_path)
    target = tmp_path / "afile.txt"
    target.write_text("x", encoding="utf-8")
    entry = store.add(str(target))
    result = Indexer(base_dir=tmp_path).build(entry, store)

    assert result.error
    assert store.get(entry.id).index_status == STATUS_FAILED
