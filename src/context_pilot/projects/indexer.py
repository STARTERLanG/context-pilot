"""项目索引构建：遍历文件夹、应用忽略规则、产出可展示的索引摘要。

索引结果存 SQLite（~/.context-pilot/index.db），每项目一张 files 表，
记录相对路径与文件大小。状态由 ProjectStore 管理（pending/running/done/failed）。

忽略规则与 retrieval.ignore 保持一致（node_modules/.git/venv 等）。
"""

import os
import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path

from context_pilot.projects.projects import (
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_RUNNING,
    ProjectStore,
)

# 与 retrieval/ignore.py 保持一致的忽略目录
_IGNORED_DIRS: frozenset[str] = frozenset(
    {
        ".git", "node_modules", "dist", "build", "venv", ".venv",
        "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache",
        ".idea", ".vscode", "target",
    }
)

_MAX_INDEX_FILES = 20000  # 单项目索引上限，防超大仓库卡死


@dataclass
class IndexResult:
    """一次索引的结果。"""

    file_count: int = 0
    total_bytes: int = 0
    duration_ms: int = 0
    error: str = ""


class Indexer:
    """把项目文件夹扫描进 SQLite 索引库。"""

    def __init__(self, base_dir: Path | None = None) -> None:
        self._index_root = base_dir or Path.home() / ".context-pilot"
        self._index_root.mkdir(parents=True, exist_ok=True)
        self._db_path = self._index_root / "index.db"

    def build(self, entry, store: ProjectStore) -> IndexResult:
        """对单个项目条目执行索引，更新其状态。同步执行，供线程调用。"""
        started = time.monotonic()
        result = IndexResult()
        project_path = Path(entry.path)

        store.set_status(entry.id, STATUS_RUNNING)

        if not project_path.exists():
            result.error = "路径不存在"
            store.set_status(entry.id, STATUS_FAILED, result.error)
            return result
        if not project_path.is_dir():
            result.error = "不是文件夹"
            store.set_status(entry.id, STATUS_FAILED, result.error)
            return result

        table = f"files_{entry.id}"
        try:
            with closing(self._connect()) as conn, conn:
                conn.execute(f"DROP TABLE IF EXISTS {table}")
                conn.execute(
                    f"CREATE TABLE {table} (path TEXT PRIMARY KEY, size INTEGER)"
                )
                files = self._walk(project_path)
                conn.executemany(
                    f"INSERT OR IGNORE INTO {table} (path, size) VALUES (?, ?)", files
                )
        except (OSError, sqlite3.Error) as exc:
            result.error = f"索引失败：{exc}"
            store.set_status(entry.id, STATUS_FAILED, result.error)
            return result

        result.file_count = len(files)
        result.total_bytes = sum(size for _, size in files)
        result.duration_ms = int((time.monotonic() - started) * 1000)
        store.set_status(entry.id, STATUS_DONE)
        return result

    def _walk(self, root: Path) -> list[tuple[str, int]]:
        files: list[tuple[str, int]] = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in _IGNORED_DIRS]
            for filename in filenames:
                path = Path(dirpath) / filename
                rel = path.relative_to(root).as_posix()
                try:
                    size = path.stat().st_size
                except OSError:
                    size = 0
                files.append((rel, size))
                if len(files) >= _MAX_INDEX_FILES:
                    break
            if len(files) >= _MAX_INDEX_FILES:
                break
        return files

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)
