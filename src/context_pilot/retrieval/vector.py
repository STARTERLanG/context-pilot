"""向量检索（PRD 6.5 Level 4 的本地近似）。

真实 Embedding 需要外部模型/端点，当前不可用。此实现用字符 n-gram 的
哈希特征向量 + 余弦相似度做语义近似，纯标准库、可离线、可测试。
作为后续接入真实 Embedding 的骨架：替换向量化函数即可，检索协议不变。
"""

import hashlib
import math
import os
from pathlib import Path

from context_pilot.core.models import ContextItem
from context_pilot.project.models import ProjectContext
from context_pilot.retrieval.ignore import is_ignored_dir, is_sensitive, is_text_candidate

_MAX_RESULTS = 15
_MAX_ITEM_CHARS = 4000
_NGRAM = 3  # 字符三元组
_HASH_BITS = 256  # 特征向量位数
_FEATURES = 1024  # 截断特征数，控制向量密度


def _features(text: str) -> list[int]:
    """把文本变成固定长度稀疏特征向量（n-gram 哈希）。"""
    lowered = text.lower()
    if len(lowered) < _NGRAM:
        return []
    features: list[int] = []
    seen: set[int] = set()
    for index in range(len(lowered) - _NGRAM + 1):
        gram = lowered[index : index + _NGRAM]
        digest = hashlib.sha256(gram.encode("utf-8")).digest()
        feature = int.from_bytes(digest[:_HASH_BITS // 8], "big")
        if feature not in seen:
            seen.add(feature)
            features.append(feature)
        if len(features) >= _FEATURES:
            break
    return features


def _cosine(a: list[int], b: list[int]) -> float:
    if not a or not b:
        return 0.0
    a_set, b_set = set(a), set(b)
    if not a_set or not b_set:
        return 0.0
    dot = len(a_set & b_set)
    norm_a = math.sqrt(len(a_set))
    norm_b = math.sqrt(len(b_set))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class VectorRetriever:
    """n-gram 哈希向量 + 余弦相似度检索。适合中文查询命中英文代码。"""

    def __init__(self, max_results: int = _MAX_RESULTS) -> None:
        self._max_results = max_results

    def search(self, query: str, project: ProjectContext) -> list[ContextItem]:
        query_features = _features(query)
        if not query_features:
            return []

        scored: list[tuple[float, ContextItem]] = []
        for dirpath, dirnames, filenames in os.walk(project.root):
            dirnames[:] = [d for d in dirnames if not is_ignored_dir(d)]
            for filename in filenames:
                path = Path(dirpath) / filename
                rel = path.relative_to(project.root)
                if is_sensitive(rel):
                    continue
                if not is_text_candidate(rel):
                    continue
                try:
                    content = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                similarity = _cosine(query_features, _features(content))
                if similarity <= 0:
                    continue
                rel_posix = rel.as_posix()
                scored.append(
                    (
                        similarity,
                        ContextItem(
                            id=f"vector:{rel_posix}",
                            type="code",
                            source=rel_posix,
                            path=rel_posix,
                            content=content[:_MAX_ITEM_CHARS],
                            relevance=similarity,
                            reason=f"向量相似度 {similarity:.2f}",
                        ),
                    )
                )

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [item for _, item in scored[: self._max_results]]
