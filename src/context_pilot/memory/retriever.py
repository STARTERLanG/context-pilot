"""记忆检索：把与查询相关的项目记忆作为上下文项返回。

实现与代码检索相同的 Retriever 协议，因此 Pipeline 对待两者完全一致。
"""

from context_pilot.core.models import ContextItem
from context_pilot.memory.models import Memory
from context_pilot.memory.store import MemoryStore
from context_pilot.project.models import ProjectContext
from context_pilot.retrieval.keyword import extract_tokens

_MAX_RESULTS = 5


def _score(memory: Memory, tokens: list[str]) -> float:
    content = memory.content.lower()
    hits = sum(1 for token in tokens if token in content)
    # 命中数为主，confidence 作次要加强度，保证高置信记忆优先
    return hits * memory.confidence


class MemoryRetriever:
    """关键词匹配项目记忆。语义检索是后续扩展点。"""

    def __init__(self, store: MemoryStore, max_results: int = _MAX_RESULTS) -> None:
        self._store = store
        self._max_results = max_results

    def search(self, query: str, project: ProjectContext) -> list[ContextItem]:
        tokens = extract_tokens(query)
        if not tokens:
            return []

        scored: list[tuple[float, Memory]] = []
        for memory in self._store.list():
            score = _score(memory, tokens)
            if score > 0:
                scored.append((score, memory))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [
            ContextItem(
                id=memory.id,
                type="memory",
                source=f"memory:{memory.type.value}",
                content=memory.content,
                relevance=score,
            )
            for score, memory in scored[: self._max_results]
        ]
