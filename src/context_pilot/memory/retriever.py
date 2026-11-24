"""记忆检索：把与查询相关的项目记忆作为上下文项返回。

实现与代码检索相同的 Retriever 协议，因此 Pipeline 对待两者完全一致。
注意分词不能直接用代码检索的 extract_tokens：它只抽 ASCII 标识符，而记忆
内容多为中文（「不要直连数据库」），纯中文查询会一个词元都抽不到、永远
匹配不上。这里额外补中文 2-gram，ASCII 词元仍复用原分词器。
"""

import re

from context_pilot.core.models import ContextItem
from context_pilot.memory.models import Memory
from context_pilot.memory.store import MemoryStore
from context_pilot.project.models import ProjectContext
from context_pilot.retrieval.keyword import extract_tokens

_MAX_RESULTS = 5
_CJK_RE = re.compile(r"[一-鿿]+")


def _tokens(text: str) -> list[str]:
    """查询分词：ASCII 标识符 + 中文 2-gram（保留 extract_tokens 的去重小写语义）。"""
    tokens = extract_tokens(text)
    for run in _CJK_RE.findall(text):
        if len(run) == 1:
            tokens.append(run)
        else:
            tokens.extend(run[i : i + 2] for i in range(len(run) - 1))
    return list(dict.fromkeys(tokens))


def _score(memory: Memory, tokens: list[str]) -> float:
    content = memory.content.lower()
    hits = sum(1 for token in tokens if token in content)
    # 命中数为主，confidence 作次要加强度，保证高置信记忆优先
    return hits * memory.confidence


class MemoryRetriever:
    """关键词匹配项目记忆 + 全局记忆。语义检索是后续扩展点。"""

    def __init__(
        self,
        store: MemoryStore,
        max_results: int = _MAX_RESULTS,
        global_store: MemoryStore | None = None,
    ) -> None:
        self._store = store
        self._global_store = global_store
        self._max_results = max_results

    def search(self, query: str, project: ProjectContext) -> list[ContextItem]:
        tokens = _tokens(query)
        if not tokens:
            return []

        stores = [self._store]
        if self._global_store is not None:
            stores.append(self._global_store)
        scored: list[tuple[float, Memory]] = []
        for store in stores:
            for memory in store.list():
                score = _score(memory, tokens)
                if score > 0:
                    scored.append((score, memory))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [
            ContextItem(
                id=memory.id,
                type="memory",
                source=f"memory:{memory.type.value}/{memory.scope}",
                content=memory.content,
                relevance=score,
                reason=(
                    f"{'全局' if memory.scope == 'global' else '项目'}记忆命中关键词，"
                    f"置信度 {memory.confidence:g}"
                ),
            )
            for score, memory in scored[: self._max_results]
        ]
