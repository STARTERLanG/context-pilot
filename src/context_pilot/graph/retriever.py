"""图检索（PRD 41：命中符号后沿边扩展上下文）。

实现 Retriever 协议。命中查询中的符号后，返回其调用/继承目标对应的
项目文件作为上下文项——形成「Relevant Context Graph」。
"""

import re
from pathlib import Path

from context_pilot.core.models import ContextItem
from context_pilot.graph.store import GraphStore
from context_pilot.project.models import ProjectContext

_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class GraphRetriever:
    """沿符号关系扩展上下文。"""

    def __init__(self, store: GraphStore) -> None:
        self._store = store

    def search(self, query: str, project: ProjectContext) -> list[ContextItem]:
        tokens = _TOKEN_RE.findall(query)
        if not tokens:
            return []

        related_files: dict[str, float] = {}
        for token in tokens:
            edges = self._store.neighbors(token)
            for edge in edges:
                # 边目标已在项目内？用文件名粗匹配
                score = 1.0 if edge.relation == "inherits" else 0.8
                related_files[edge.target] = max(
                    related_files.get(edge.target, 0.0), score
                )

        items: list[ContextItem] = []
        for target, score in related_files.items():
            # 在项目里定位符号所在文件（简化：按符号名全局搜文件）
            matched = self._find_symbol_file(target, project.root)
            if matched is None:
                continue
            rel = matched.relative_to(project.root).as_posix()
            try:
                content = matched.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            items.append(
                ContextItem(
                    id=f"graph:{rel}",
                    type="code",
                    source=rel,
                    path=rel,
                    content=content[:4000],
                    relevance=score,
                    reason=f"图扩展：{target}（关系 {edge.relation}）",
                )
            )
        return items

    def _find_symbol_file(self, symbol: str, root: Path) -> Path | None:
        """在项目文件中定位包含该符号定义的文件（粗糙：文件级扫描）。"""
        candidates: list[Path] = []
        for path in root.rglob("*.py"):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if symbol in text:
                candidates.append(path)
        if not candidates:
            return None
        # 优先匹配 class X: 或 def X( 定义形态
        for path in candidates:
            text = path.read_text(encoding="utf-8", errors="replace")
            if re.search(rf"class\s+{symbol}\b|def\s+{symbol}\b", text):
                return path
        return candidates[0]
