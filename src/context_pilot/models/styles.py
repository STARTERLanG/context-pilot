"""输出风格预设（Output Styles）：用户自定义增删改的持久化。

存 SQLite（~/.context-pilot/styles.db）。首次启动把内置三条预设（default /
concise / natural）作为种子写入，用户可在此基础上增删改。风格预设决定
「详细程度 / 格式自由度 / 长度上限」三件事，供主页面「风格」下拉与增强管线使用。
"""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from context_pilot.core.models import OUTPUT_STYLES, OutputStyle

_DEFAULT_DIR = Path.home() / ".context-pilot"
_DB_NAME = "styles.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS output_styles (
    id          TEXT PRIMARY KEY,
    label       TEXT NOT NULL,
    instruction TEXT NOT NULL DEFAULT '',
    max_tokens  INTEGER NOT NULL DEFAULT 6000,
    mode        TEXT NOT NULL DEFAULT 'task',
    description TEXT NOT NULL DEFAULT '',
    builtin     INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
)
"""


@dataclass(frozen=True)
class StyleRecord:
    """一条风格预设的持久化记录（含 builtin 标记，供界面区分内置/自定义）。"""

    key: str
    label: str
    instruction: str
    max_tokens: int
    builtin: bool
    mode: str = "task"
    description: str = ""


class StyleStore:
    """风格预设的 SQLite CRUD。"""

    def __init__(self, base_dir: Path | None = None) -> None:
        self._path = (base_dir or _DEFAULT_DIR) / _DB_NAME
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn, conn:
            conn.execute(_SCHEMA)
            self._migrate(conn)
        self._seed()

    def _migrate(self, conn: sqlite3.Connection) -> None:
        """轻量迁移：为旧库补 mode / description 两列（幂等）。"""
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(output_styles)")}
        if "mode" not in cols:
            conn.execute("ALTER TABLE output_styles ADD COLUMN mode TEXT NOT NULL DEFAULT 'task'")
        if "description" not in cols:
            conn.execute("ALTER TABLE output_styles ADD COLUMN description TEXT NOT NULL DEFAULT ''")

    @property
    def path(self) -> Path:
        return self._path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def _seed(self) -> None:
        """同步内置预设：补新增、删废弃、回填 mode/description 元数据。

        - 新增内置 key（如 basic/professional/planning）→ 插入。
        - 废弃的内置 key（如 concise/natural，已从 OUTPUT_STYLES 移除）→ 删除，
          因为它们不再对应任何优化模式。
        - 已存在内置 key 的 label/instruction/max_tokens 保留用户编辑，但
          mode/description 是模式元数据，始终回填为代码定义值。
        """
        builtin_keys = {p.key for p in OUTPUT_STYLES}
        with closing(self._connect()) as conn, conn:
            # 删除已废弃的内置预设（builtin=1 且不在当前 OUTPUT_STYLES 中）
            for row in conn.execute(
                "SELECT id FROM output_styles WHERE builtin = 1"
            ).fetchall():
                if row["id"] not in builtin_keys:
                    conn.execute("DELETE FROM output_styles WHERE id = ?", (row["id"],))

            existing = {
                row["id"] for row in conn.execute("SELECT id FROM output_styles")
            }
            for preset in OUTPUT_STYLES:
                if preset.key not in existing:
                    conn.execute(
                        "INSERT INTO output_styles"
                        " (id, label, instruction, max_tokens, mode, description,"
                        "  builtin, created_at)"
                        " VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
                        (
                            preset.key,
                            preset.label,
                            preset.instruction,
                            preset.max_tokens,
                            preset.mode,
                            preset.description,
                            datetime.now().isoformat(timespec="seconds"),
                        ),
                    )
                else:
                    # 已存在：回填 mode/description（模式元数据以代码为准）
                    conn.execute(
                        "UPDATE output_styles SET mode = ?, description = ? WHERE id = ?",
                        (preset.mode, preset.description, preset.key),
                    )

    def list(self) -> list[OutputStyle]:
        """返回全部预设（按内置顺序 + 创建时间）。"""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM output_styles ORDER BY builtin DESC, created_at ASC"
            ).fetchall()
        return [self._row_to_style(row) for row in rows]

    def records(self) -> list[StyleRecord]:
        """返回带 builtin 标记的记录（供设置界面展示区分）。"""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM output_styles ORDER BY builtin DESC, created_at ASC"
            ).fetchall()
        return [
            StyleRecord(
                key=row["id"],
                label=row["label"],
                instruction=row["instruction"],
                max_tokens=row["max_tokens"],
                builtin=bool(row["builtin"]),
                mode=row["mode"] if "mode" in row.keys() else "task",
                description=row["description"] if "description" in row.keys() else "",
            )
            for row in rows
        ]

    def get(self, key: str) -> OutputStyle | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM output_styles WHERE id = ?", (key,)
            ).fetchone()
        if row is None:
            return None
        return self._row_to_style(row)

    @staticmethod
    def _row_to_style(row: sqlite3.Row) -> OutputStyle:
        return OutputStyle(
            key=row["id"],
            label=row["label"],
            instruction=row["instruction"],
            max_tokens=row["max_tokens"],
            mode=row["mode"] if "mode" in row.keys() else "task",
            description=row["description"] if "description" in row.keys() else "",
        )

    def add(self, *, label: str, instruction: str, max_tokens: int) -> OutputStyle:
        """新增一条自定义预设（内置 key 用 uuid 生成）。

        自定义预设默认 mode=task（结构化增强），description 留空。
        """
        if not label.strip():
            raise ValueError("预设名称不能为空")
        key = "custom-" + uuid.uuid4().hex[:8]
        now = datetime.now().isoformat(timespec="seconds")
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO output_styles"
                " (id, label, instruction, max_tokens, mode, description,"
                "  builtin, created_at)"
                " VALUES (?, ?, ?, ?, 'task', '', 0, ?)",
                (key, label.strip(), instruction, max_tokens, now),
            )
        return OutputStyle(
            key=key, label=label.strip(), instruction=instruction,
            max_tokens=max_tokens, mode="task", description="",
        )

    def update(
        self, key: str, *, label: str, instruction: str, max_tokens: int
    ) -> bool:
        """更新一条预设；不存在返回 False。"""
        if not label.strip():
            raise ValueError("预设名称不能为空")
        with closing(self._connect()) as conn, conn:
            cur = conn.execute(
                "UPDATE output_styles SET label = ?, instruction = ?, max_tokens = ?"
                " WHERE id = ?",
                (label.strip(), instruction, max_tokens, key),
            )
        return cur.rowcount > 0

    def delete(self, key: str) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute("DELETE FROM output_styles WHERE id = ?", (key,))
