"""项目记忆的 SQLite 持久化。路径与库名对齐 PRD 19 / 20。

每次操作独立开关连接：SQLite 开销极小，避免长连接带来的生命周期与线程问题
（记忆会被工作线程读写）。
"""

import hashlib
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path

from context_pilot.memory.models import Memory, MemoryType

_DB_DIR = Path.home() / ".context-pilot"
_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id          TEXT PRIMARY KEY,
    type        TEXT NOT NULL,
    content     TEXT NOT NULL,
    scope       TEXT NOT NULL DEFAULT 'project',
    source      TEXT NOT NULL DEFAULT 'manual',
    confidence  REAL NOT NULL DEFAULT 1.0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
)
"""


def project_hash(project_root: Path | str) -> str:
    """按项目绝对路径生成稳定哈希，用于隔离不同项目的记忆。"""
    resolved = str(Path(project_root).resolve())
    return hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:16]


def db_path(project_root: Path | str, base_dir: Path | None = None) -> Path:
    """按项目路径哈希定位记忆库；base_dir 可覆盖默认根（测试用）。"""
    root = base_dir or _DB_DIR
    return root / project_hash(project_root) / "memory.db"


class MemoryStore:
    """一个项目对应一个 SQLite 库。"""

    def __init__(self, project_root: Path | str, base_dir: Path | None = None) -> None:
        self._path = db_path(project_root, base_dir)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn, conn:
            conn.execute(_SCHEMA)

    @property
    def path(self) -> Path:
        return self._path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def add(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.PROJECT_FACT,
        source: str = "manual",
        confidence: float = 1.0,
    ) -> Memory:
        text = content.strip()
        if not text:
            raise ValueError("记忆内容不能为空")
        now = Memory.now()
        memory = Memory(
            id=uuid.uuid4().hex,
            type=memory_type,
            content=text,
            source=source,
            confidence=confidence,
            created_at=now,
            updated_at=now,
        )
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO memories"
                " (id, type, content, scope, source, confidence, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    memory.id,
                    memory.type.value,
                    memory.content,
                    memory.scope,
                    memory.source,
                    memory.confidence,
                    memory.created_at,
                    memory.updated_at,
                ),
            )
        return memory

    def list(self) -> list[Memory]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM memories ORDER BY created_at DESC"
            ).fetchall()
        return [_row_to_memory(row) for row in rows]

    def delete(self, memory_id: str) -> bool:
        with closing(self._connect()) as conn, conn:
            cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        return cursor.rowcount > 0


def _row_to_memory(row: sqlite3.Row) -> Memory:
    return Memory(
        id=row["id"],
        type=MemoryType(row["type"]),
        content=row["content"],
        scope=row["scope"],
        source=row["source"],
        confidence=row["confidence"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
