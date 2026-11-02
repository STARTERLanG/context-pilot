"""项目条目存储与索引单测。"""

import os
import sqlite3
import time
from contextlib import closing
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


def test_index_walk_excludes_ignored_dirs_and_secrets(tmp_path):
    """索引遍历复用 retrieval.ignore：忽略目录 + 敏感文件都不入库。

    此前 indexer 手抄了一份目录名单（漏 target）且完全没有敏感过滤，
    会把 .env 这类文件扫进 index.db。
    """
    project = tmp_path / "proj"
    (project / "src").mkdir(parents=True)
    (project / "node_modules").mkdir(parents=True)
    (project / "target").mkdir()  # 先前被漏掉的构建目录

    (project / "src" / "app.py").write_text("x", encoding="utf-8")
    (project / "node_modules" / "dep.py").write_text("x", encoding="utf-8")
    (project / "target" / "out.bin").write_text("x", encoding="utf-8")
    (project / ".env").write_text("SECRET=1", encoding="utf-8")
    (project / "id_rsa").write_text("key", encoding="utf-8")

    walk = Indexer(base_dir=tmp_path / "idx")._walk(project)
    walked = {row[0]: row[1] for row in walk.changed}
    paths = "\n".join(walked)
    assert walk.truncated is False

    assert "src/app.py" in walked
    assert "node_modules" not in paths
    assert "target/" not in paths
    assert ".env" not in walked
    assert "id_rsa" not in walked


# ── 增量索引（CLAUDE.md:86）──────────────────────────────────────────


def _indexed_project(tmp_path, files: dict[str, str]):
    """建一个含指定文件的项目，返回 (entry, store, Indexer)。"""
    store = _store(tmp_path)
    project = tmp_path / "app"
    project.mkdir()
    for name, content in files.items():
        target = project / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    entry = store.add(str(project))
    return entry, store, Indexer(base_dir=tmp_path / "idx")


def test_rebuild_skips_unchanged_files(tmp_path):
    """二次索引：未变动的文件不写库（changed=0，reused 全部沿用）。"""
    entry, store, indexer = _indexed_project(tmp_path, {"a.py": "a", "b.py": "b"})

    first = indexer.build(entry, store)
    assert first.changed == 2
    assert first.file_count == 2

    second = indexer.build(entry, store)
    assert second.changed == 0  # 全都没变
    assert second.reused == 2
    assert second.scanned == 2  # 仍然遍历并 stat 了每个文件
    assert second.file_count == 2
    assert store.get(entry.id).index_status == STATUS_DONE


def test_rebuild_picks_up_modified_file(tmp_path):
    """内容改动会导致 size 变化 → 该文件被重新写库，其余不变。"""
    entry, store, indexer = _indexed_project(tmp_path, {"a.py": "a", "b.py": "b"})
    indexer.build(entry, store)

    (Path(entry.path) / "a.py").write_text("a 改过了会长一些", encoding="utf-8")
    result = indexer.build(entry, store)

    assert result.changed == 1
    assert result.reused == 1
    assert result.file_count == 2
    assert result.total_bytes > 2  # 新尺寸已入库


def test_rebuild_detects_same_size_edit(tmp_path):
    """陷阱用例：等长改写 mtime 不变时无法察觉，但 mtime 变化必须抓到。

    若只按 size 判定，「abc」改成「xyz」会被漏掉；这里用 touch 强制改 mtime
    模拟真实写入，验证 mtime 维度确实参与判定。
    """
    entry, store, indexer = _indexed_project(tmp_path, {"a.py": "abc"})
    indexer.build(entry, store)

    target = Path(entry.path) / "a.py"
    target.write_text("xyz", encoding="utf-8")  # 同尺寸，不同内容
    os.utime(target, (time.time() + 10, time.time() + 10))

    result = indexer.build(entry, store)
    assert result.changed == 1


def test_rebuild_removes_deleted_files(tmp_path):
    """磁盘上删掉的文件要从索引库清掉，否则会留下幽灵条目。"""
    entry, store, indexer = _indexed_project(tmp_path, {"a.py": "a", "b.py": "b"})
    indexer.build(entry, store)

    (Path(entry.path) / "b.py").unlink()
    result = indexer.build(entry, store)

    assert result.removed == 1
    assert result.file_count == 1
    assert indexer.build(entry, store).file_count == 1  # 收敛，不再重复删除


def test_rebuild_migrates_legacy_two_column_table(tmp_path):
    """旧版本建的 path/size 两列表缺 mtime，应自动重建而非静默出错。"""
    index_root = tmp_path / "idx"
    index_root.mkdir()
    entry, store, indexer = _indexed_project(tmp_path, {"a.py": "a"})

    with closing(sqlite3.connect(indexer._db_path)) as conn, conn:
        table = f"files_{entry.id}"
        conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.execute(f"CREATE TABLE {table} (path TEXT PRIMARY KEY, size INTEGER)")
        conn.execute(f"INSERT INTO {table} (path, size) VALUES ('a.py', 1)")

    result = indexer.build(entry, store)

    assert result.error == ""
    assert result.file_count == 1  # 重建后正确，没有把旧数据丢成空
    # 表结构已升级：再索引一次应走增量而非再次全量
    assert indexer.build(entry, store).reused == 1
