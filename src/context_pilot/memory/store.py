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
# 全局记忆库的固定目录名：与任何项目哈希不同（项目哈希是 16 位十六进制），
# 用带前缀的名字避免与真实项目目录冲突。
_GLOBAL_KEY = "_global"
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


def global_db_path(base_dir: Path | None = None) -> Path:
    """全局记忆库路径：不随项目变化，存放跨项目通用的偏好/约定。"""
    root = base_dir or _DB_DIR
    return root / _GLOBAL_KEY / "memory.db"


def db_path(project_root: Path | str, base_dir: Path | None = None) -> Path:
    """按项目路径哈希定位记忆库；base_dir 可覆盖默认根（测试用）。"""
    root = base_dir or _DB_DIR
    return root / project_hash(project_root) / "memory.db"


class MemoryStore:
    """一个 SQLite 记忆库。默认按项目隔离；`scope="global"` 时用全局库。

    两类库表结构完全相同，`scope` 字段记录每条记忆的归属，便于 UI 统一展示。
    """

    def __init__(
        self,
        project_root: Path | str,
        base_dir: Path | None = None,
        *,
        scope: str = "project",
    ) -> None:
        if scope not in ("project", "global"):
            raise ValueError(f"未知记忆范围：{scope}")
        self._scope = scope
        self._path = (
            global_db_path(base_dir) if scope == "global" else db_path(project_root, base_dir)
        )
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn, conn:
            conn.execute(_SCHEMA)

    @property
    def path(self) -> Path:
        return self._path

    @property
    def scope(self) -> str:
        return self._scope

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
            scope=self._scope,
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

    def update(
        self,
        memory_id: str,
        content: str,
        memory_type: MemoryType | None = None,
    ) -> bool:
        """修改一条记忆的正文/类型。返回是否命中。空正文一律拒绝。"""
        text = content.strip()
        if not text:
            raise ValueError("记忆内容不能为空")
        with closing(self._connect()) as conn, conn:
            if memory_type is None:
                cursor = conn.execute(
                    "UPDATE memories SET content = ?, updated_at = ? WHERE id = ?",
                    (text, Memory.now(), memory_id),
                )
            else:
                cursor = conn.execute(
                    "UPDATE memories SET content = ?, type = ?, updated_at = ? WHERE id = ?",
                    (text, memory_type.value, Memory.now(), memory_id),
                )
        return cursor.rowcount > 0

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
