"""项目索引条目：本地文件夹路径的持久化管理。

存 SQLite（~/.context-pilot/projects.db）。每条记录一个被增强项目的绝对路径、
索引状态（pending/running/done/failed）与错误原因。索引的生成逻辑在 indexer.py。
"""

import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_DIR = Path.home() / ".context-pilot"
_DB_NAME = "projects.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS project_entries (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    path        TEXT NOT NULL UNIQUE,
    index_status TEXT NOT NULL DEFAULT 'pending',
    error       TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
)
"""

# 索引状态常量（供 UI 与 indexer 复用）
STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_FAILED = "failed"


@dataclass(frozen=True)
class ProjectEntry:
    """一个待索引的项目。index_status 为四态之一。"""

    id: str
    name: str
    path: str
    index_status: str = STATUS_PENDING
    error: str = ""
    created_at: str = ""


class ProjectStore:
    """项目目录的 SQLite CRUD。"""

    def __init__(self, base_dir: Path | None = None) -> None:
        self._path = (base_dir or _DEFAULT_DIR) / _DB_NAME
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn, conn:
            conn.execute(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def list(self) -> list[ProjectEntry]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM project_entries ORDER BY created_at DESC"
            ).fetchall()
        return [_row_to_entry(row) for row in rows]

    def get(self, entry_id: str) -> ProjectEntry | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM project_entries WHERE id = ?", (entry_id,)
            ).fetchone()
        return _row_to_entry(row) if row else None

    def get_by_path(self, path: str) -> ProjectEntry | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM project_entries WHERE path = ?", (path,)
            ).fetchone()
        return _row_to_entry(row) if row else None

    def add(self, path: str) -> ProjectEntry:
        """新增一条项目记录。重复路径返回既有记录（不报错）。"""
        resolved = str(Path(path).resolve())
        existing = self.get_by_path(resolved)
        if existing is not None:
            return existing

        now = _now()
        entry_id = uuid.uuid4().hex[:12]
        name = Path(resolved).name or resolved
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO project_entries"
                " (id, name, path, index_status, error, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (entry_id, name, resolved, STATUS_PENDING, "", now),
            )
        entry = self.get(entry_id)
        assert entry is not None
        return entry

    def set_status(self, entry_id: str, status: str, error: str = "") -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "UPDATE project_entries SET index_status = ?, error = ? WHERE id = ?",
                (status, error, entry_id),
            )

    def delete(self, entry_id: str) -> bool:
        with closing(self._connect()) as conn, conn:
            cursor = conn.execute(
                "DELETE FROM project_entries WHERE id = ?", (entry_id,)
            )
        return cursor.rowcount > 0


def _now() -> str:
    from datetime import datetime

    return datetime.now().isoformat(timespec="seconds")


def _row_to_entry(row: sqlite3.Row) -> ProjectEntry:
    return ProjectEntry(
        id=row["id"],
        name=row["name"],
        path=row["path"],
        index_status=row["index_status"],
        error=row["error"],
        created_at=row["created_at"],
    )
