"""基于 Tree-sitter 的 AST 符号检索（PRD 6.5 Level 3）。

解析 Python 文件的 Class / Function / Method / Import，建立符号索引，
再按查询中的标识符词元匹配符号名，返回对应文件片段作为上下文。
"""

import os
import re
from pathlib import Path

from tree_sitter import Language, Parser, Query, QueryCursor

import tree_sitter_python as tsp

from context_pilot.core.models import ContextItem
from context_pilot.project.models import ProjectContext
from context_pilot.retrieval.ignore import is_ignored_dir, is_sensitive

_MAX_SYMBOLS_PER_FILE = 200
_MAX_ITEM_CHARS = 4000

_PY_QUERY = Query(
    Language(tsp.language()),
    """
    (class_definition name: (identifier) @symbol)
    (function_definition name: (identifier) @symbol)
    (import_statement name: (dotted_name) @symbol)
    (import_from_statement module_name: (dotted_name) @symbol)
    """,
)

_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _symbol_matches(query: str, symbol: str) -> bool:
    """查询中的标识符与符号名做大小写不敏感子串匹配。"""
    lowered = symbol.lower()
    return any(token.lower() in lowered for token in _TOKEN_RE.findall(query))


class AstRetriever:
    """用 Tree-sitter 提取符号，按符号名匹配查询。"""

    def __init__(self) -> None:
        self._parser = Parser(Language(tsp.language()))
        self._cursor = QueryCursor(_PY_QUERY)
        self._cache: dict[Path, list[str]] = {}

    def _symbols(self, path: Path) -> list[str]:
        if path in self._cache:
            return self._cache[path]
        try:
            source = path.read_bytes()
        except OSError:
            return []
        tree = self._parser.parse(source)
        captures = self._cursor.captures(tree.root_node)
        symbols = [
            source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
            for name, nodes in captures.items()
            for node in nodes
            if name == "symbol"
        ][:_MAX_SYMBOLS_PER_FILE]
        self._cache[path] = symbols
        return symbols

    def search(self, query: str, project: ProjectContext) -> list[ContextItem]:
        if not _TOKEN_RE.search(query):
            return []

        items: list[ContextItem] = []
        for dirpath, dirnames, filenames in os.walk(project.root):
            dirnames[:] = [d for d in dirnames if not is_ignored_dir(d)]
            for filename in filenames:
                if not filename.endswith(".py"):
                    continue
                path = Path(dirpath) / filename
                rel = path.relative_to(project.root)
                if is_sensitive(rel):
                    continue
                symbols = self._symbols(path)
                if not symbols:
                    continue
                matched = [s for s in symbols if _symbol_matches(query, s)]
                if not matched:
                    continue
                try:
                    content = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                rel_posix = rel.as_posix()
                items.append(
                    ContextItem(
                        id=f"ast:{rel_posix}",
                        type="symbol",
                        source=rel_posix,
                        path=rel_posix,
                        content=content[:_MAX_ITEM_CHARS],
                        relevance=float(len(matched)),
                        reason="AST 符号命中：" + "、".join(matched[:5]),
                    )
                )
        items.sort(key=lambda item: item.relevance, reverse=True)
        return items
