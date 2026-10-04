"""关键词 + 路径匹配检索器。对应 PRD 6.5 的 Level 1 / Level 2。

纯 Python 实现，不依赖 ripgrep（本机未安装）；后续可替换为 ripgrep 版本而接口不变。

已知局限：从查询中提取的是 ASCII 标识符词元，纯中文查询匹配不到英文代码；
语义检索（PRD Level 4 向量）是后续用来补这块的扩展点。
"""

import os
import re
from pathlib import Path

from context_pilot.core.models import ContextItem
from context_pilot.project.models import ProjectContext
from context_pilot.retrieval.ignore import is_ignored_dir, is_sensitive, is_text_candidate

_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")

_MAX_RESULTS = 20
_MAX_ITEM_CHARS = 4000
_PATH_WEIGHT = 1.0
_NAME_WEIGHT = 3.0
_CONTENT_WEIGHT = 0.5
_CONTENT_HITS_CAP = 5


def extract_tokens(query: str) -> list[str]:
    """从查询提取 ASCII 标识符词元（去重、小写）。"""
    return list(dict.fromkeys(t.lower() for t in _TOKEN_RE.findall(query)))


def _score(rel_path: str, text: str, tokens: list[str]) -> float:
    path = Path(rel_path)
    name = path.name.lower()
    parent = str(path.parent).lower()
    score = 0.0
    for token in tokens:
        if token in name:
            score += _NAME_WEIGHT
        elif token in parent:
            score += _PATH_WEIGHT
        hits = min(text.lower().count(token), _CONTENT_HITS_CAP)
        score += hits * _CONTENT_WEIGHT
    return score


def _iter_candidate_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not is_ignored_dir(d)]
        for filename in filenames:
            path = Path(dirpath) / filename
            rel = path.relative_to(root)
            if is_sensitive(rel):
                continue
            if not is_text_candidate(rel):
                continue
            yield path, rel.as_posix()


class KeywordRetriever:
    """按关键词在文件路径与内容中的命中度排序，返回前 N 个文件。"""

    def __init__(self, max_results: int = _MAX_RESULTS) -> None:
        self._max_results = max_results

    def search(self, query: str, project: ProjectContext) -> list[ContextItem]:
        tokens = extract_tokens(query)
        if not tokens:
            return []

        scored: list[tuple[float, ContextItem]] = []
        for path, rel in _iter_candidate_files(project.root):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            score = _score(rel, text, tokens)
            if score <= 0:
                continue
            scored.append(
                (
                    score,
                    ContextItem(
                        id=rel,
                        type="code",
                        source=rel,
                        path=rel,
                        content=text[:_MAX_ITEM_CHARS],
                        relevance=score,
                    ),
                )
            )

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [item for _, item in scored[: self._max_results]]
