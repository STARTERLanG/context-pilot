"""用 Tree-sitter 从 Python 源码构建符号与调用/继承边（PRD 41 的 Code Graph）。"""

import os
import re
from pathlib import Path

from tree_sitter import Language, Parser, Query, QueryCursor

import tree_sitter_python as tsp

from context_pilot.graph.models import GraphEdge, SymbolRef
from context_pilot.retrieval.ignore import is_ignored_dir, is_sensitive

_QUERY = Query(
    Language(tsp.language()),
    """
    (class_definition name: (identifier) @class.name)
    (class_definition
      name: (identifier) @class.name
      superclasses: (argument_list (identifier) @class.base))
    (function_definition name: (identifier) @fn.name)
    (decorated_definition (function_definition name: (identifier) @fn.name))
    """,
)

_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class CodeGraphBuilder:
    """解析项目，产出符号与关系边。"""

    def __init__(self) -> None:
        self._parser = Parser(Language(tsp.language()))
        self._cursor = QueryCursor(_QUERY)

    def _parse_file(self, path: Path, rel: Path) -> tuple[list[SymbolRef], list[GraphEdge]] | None:
        try:
            source = path.read_bytes()
        except OSError:
            return None
        tree = self._parser.parse(source)
        root = tree.root_node
        captures = self._cursor.captures(root)

        rel_posix = rel.as_posix()
        symbols: list[SymbolRef] = []
        for kind, label in (("class", "class.name"), ("function", "fn.name")):
            for node in captures.get(label, []):
                name = source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
                line = root.start_point.row + node.start_point.row + 1
                symbols.append(SymbolRef(name, kind, rel_posix, line))

        edges: list[GraphEdge] = []
        for base_node in captures.get("class.base", []):
            base = source[base_node.start_byte:base_node.end_byte].decode(
                "utf-8", errors="replace"
            )
            # 找到所属的 class
            class_node = base_node.parent
            while class_node is not None and class_node.type != "class_definition":
                class_node = class_node.parent
            if class_node is None:
                continue
            class_name_node = class_node.child_by_field_name("name")
            if class_name_node is None:
                continue
            class_name = source[class_name_node.start_byte:class_name_node.end_byte].decode(
                "utf-8", errors="replace"
            )
            edges.append(GraphEdge(class_name, base, "inherits"))

        return symbols, edges

    def build(self, project_root: Path) -> tuple[list[SymbolRef], list[GraphEdge]]:
        symbols: list[SymbolRef] = []
        edges: list[GraphEdge] = []
        for dirpath, dirnames, filenames in os.walk(project_root):
            dirnames[:] = [d for d in dirnames if not is_ignored_dir(d)]
            for filename in filenames:
                if not filename.endswith(".py"):
                    continue
                path = Path(dirpath) / filename
                rel = path.relative_to(project_root)
                if is_sensitive(rel):
                    continue
                result = self._parse_file(path, rel)
                if result is None:
                    continue
                file_symbols, file_edges = result
                symbols.extend(file_symbols)
                edges.extend(file_edges)
        return symbols, edges
