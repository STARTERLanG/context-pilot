"""Code Graph 的 SQLite 存储（PRD 20：nodes/edges 表）。"""

import sqlite3
from contextlib import closing
from pathlib import Path

from context_pilot.graph.models import GraphEdge, SymbolRef

_SCHEMA = """
CREATE TABLE IF NOT EXISTS symbols (
    name    TEXT NOT NULL,
    kind    TEXT NOT NULL,
    file    TEXT NOT NULL,
    line    INTEGER NOT NULL,
    PRIMARY KEY (name, file, line)
);
CREATE TABLE IF NOT EXISTS edges (
    source   TEXT NOT NULL,
    target   TEXT NOT NULL,
    relation TEXT NOT NULL,
    PRIMARY KEY (source, target, relation)
);
"""


class GraphStore:
    """一个项目一个图库，建表、写边、查邻居。"""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn, conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)

    def replace_all(self, symbols: list[SymbolRef], edges: list[GraphEdge]) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute("DELETE FROM symbols")
            conn.execute("DELETE FROM edges")
            conn.executemany(
                "INSERT OR IGNORE INTO symbols (name, kind, file, line) VALUES (?, ?, ?, ?)",
                [(s.name, s.kind, s.file, s.line) for s in symbols],
            )
            conn.executemany(
                "INSERT OR IGNORE INTO edges (source, target, relation) VALUES (?, ?, ?)",
                [(e.source, e.target, e.relation) for e in edges],
            )

    def neighbors(self, name: str, relation: str | None = None) -> list[GraphEdge]:
        """返回以 name 为源的所有边（可选按 relation 过滤）。"""
        with closing(self._connect()) as conn:
            if relation:
                rows = conn.execute(
                    "SELECT source, target, relation FROM edges WHERE source = ? AND relation = ?",
                    (name, relation),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT source, target, relation FROM edges WHERE source = ?", (name,)
                ).fetchall()
        return [GraphEdge(r[0], r[1], r[2]) for r in rows]
