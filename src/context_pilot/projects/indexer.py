"""项目索引构建：遍历文件夹、应用忽略规则、产出可展示的索引摘要。

索引结果存 SQLite（~/.context-pilot/index.db），每项目一张 files 表，
记录相对路径与文件大小。状态由 ProjectStore 管理（pending/running/done/failed）。

忽略规则与 retrieval.ignore 保持一致（node_modules/.git/venv 等）。

**增量**：再次索引时只对 size 或 mtime 变化的文件写库，未变动的沿用旧记录
（CLAUDE.md:86）。判定用 size + mtime_ns 双条件——只看 size 会漏掉同尺寸的内容
改动，只看 mtime 则 touch 一下就误判为已变。
"""

import os
import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from context_pilot.core.logging_setup import get_logger
from context_pilot.projects.projects import (
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_RUNNING,
    ProjectStore,
)
from context_pilot.retrieval.ignore import is_ignored_dir, is_sensitive

_MAX_INDEX_FILES = 20000  # 单项目索引上限，防超大仓库卡死

# 表结构。mtime 存 st_mtime_ns，必须是 INTEGER：
# SQLite 的 REAL 只有约 15 位有效数字，纳秒时间戳约 1.7e18 会被截断，
# 回读后与原值不相等 → 每次都误判为「已变更」，增量形同全量。
_TABLE_SCHEMA = "(path TEXT PRIMARY KEY, size INTEGER, mtime INTEGER)"
_EXPECTED_COLUMNS = {"path": "TEXT", "size": "INTEGER", "mtime": "INTEGER"}


@dataclass(frozen=True)
class WalkResult:
    """一次遍历的产物。

    ``changed`` 与 ``present`` 必须分开返回：前者是「要写库的」，后者是
    「磁盘上真实存在的」。只拿 changed 去算删除，会把未变更的文件当成已
    删除清理掉——正是这两个集合混淆导致的第一版 bug。
    """

    changed: list  # [(path, size, mtime_ns)] 需要写库的新增/变更条目
    present: dict  # {path: (size, mtime_ns)} 磁盘上所有未被忽略/敏感的文件
    scanned: int  # 实际 stat 的文件数
    truncated: bool  # 是否触及 _MAX_INDEX_FILES 上限


@dataclass
class IndexResult:
    """一次索引的结果。"""

    file_count: int = 0  # 索引库中该项目最终的条目数
    total_bytes: int = 0
    duration_ms: int = 0
    error: str = ""
    scanned: int = 0  # 本次实际 stat 的文件数（含判定为「未变」的）
    changed: int = 0  # 真正写库的新增/变更条目数
    reused: int = 0  # 沿用旧记录的未变条目数
    removed: int = 0  # 磁盘上已不存在、从库中删除的条目数


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
                previous = self._load_previous(conn, table)
                if previous is None:  # 表不存在或是旧的双列结构 → 全量重建
                    conn.execute(f"DROP TABLE IF EXISTS {table}")
                    conn.execute(f"CREATE TABLE {table} {_TABLE_SCHEMA}")
                    previous = {}

                walk = self._walk(project_path, previous)
                result.scanned = walk.scanned
                conn.executemany(
                    f"INSERT OR REPLACE INTO {table} (path, size, mtime) "
                    "VALUES (?, ?, ?)",
                    walk.changed,
                )
                result.changed = len(walk.changed)

                # 清理磁盘上已消失的旧记录。扫描被上限截断时不能清理——
                # 没扫到的部分不在 files 里，会被误判成已删除。
                if walk.truncated:
                    get_logger(__name__).warning(
                        "项目索引达到上限被截断，跳过过期条目清理：%s", entry.path
                    )
                else:
                    # 依据「磁盘上实际存在」判定过期，而非「本次写库」的集合
                    stale = [(p,) for p in previous if p not in walk.present]
                    if stale:
                        conn.executemany(
                            f"DELETE FROM {table} WHERE path = ?", stale
                        )
                        result.removed = len(stale)

                # 沿用旧记录的数量 = 磁盘上存在但未写库的那些（首次索引时为 0）
                result.reused = len(walk.present) - result.changed
                row = conn.execute(
                    f"SELECT COUNT(*), COALESCE(SUM(size), 0) FROM {table}"
                ).fetchone()
                result.file_count = row[0]
                result.total_bytes = row[1]
        except (OSError, sqlite3.Error) as exc:
            result.error = f"索引失败：{exc}"
            get_logger(__name__).exception("项目索引失败：%s | %s", entry.path, exc)
            store.set_status(entry.id, STATUS_FAILED, result.error)
            return result

        result.duration_ms = int((time.monotonic() - started) * 1000)
        store.set_status(entry.id, STATUS_DONE)
        return result

    @staticmethod
    def _load_previous(conn: sqlite3.Connection, table: str) -> dict | None:
        """读已有索引供增量比对。返回 None 表示需要全量重建。

        None 有两种情况：表压根不存在（首次索引），或表结构不是当前版本
        （旧版建的只有 path/size 两列，或 mtime 用了 REAL）——一律全量重建，
        不做迁移，索引本来就可以随时重算。
        """
        try:
            info = conn.execute(f"PRAGMA table_info({table})").fetchall()
        except sqlite3.Error:
            return None
        # PRAGMA 返回 (cid, name, type, notnull, dflt_value, pk)
        column_types = {row[1]: (row[2] or "").upper() for row in info}
        if any(column_types.get(name) != type_ for name, type_ in _EXPECTED_COLUMNS.items()):
            return None
        return {
            row[0]: (row[1], row[2])
            for row in conn.execute(f"SELECT path, size, mtime FROM {table}")
        }

    def _walk(self, root: Path, previous: dict | None = None) -> WalkResult:
        """遍历项目文件，返回「待写库条目」与「磁盘上实际条目」两份结果。

        忽略目录与敏感文件判定都直接复用 retrieval/ignore.py，此前这里
        手抄了一份目录名单（且漏了 target），并没有敏感过滤——会把 .env
        这类文件也扫进索引库。

        ``previous`` 为 {相对路径: (size, mtime_ns)}；命中且两者都一致的文件
        视为未变更，不进入返回列表，由调用方直接沿用旧记录。
        """
        previous = previous or {}
        changed: list[tuple[str, int, int]] = []
        present: dict[str, tuple[int, int]] = {}
        scanned = 0
        truncated = False
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not is_ignored_dir(d)]
            for filename in filenames:
                path = Path(dirpath) / filename
                rel = path.relative_to(root)
                if is_sensitive(rel):
                    continue
                scanned += 1
                try:
                    stat = path.stat()
                    size, mtime = stat.st_size, stat.st_mtime_ns
                except OSError:
                    size, mtime = 0, 0
                key = rel.as_posix()
                present[key] = (size, mtime)
                # 未变更：沿用旧记录，不进入待写库列表
                if previous.get(key) == (size, mtime):
                    continue
                changed.append((key, size, mtime))
                if len(changed) >= _MAX_INDEX_FILES:
                    truncated = True
                    break
            if truncated:
                break
        return WalkResult(changed, present, scanned, truncated)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)
