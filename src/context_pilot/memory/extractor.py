"""从对话/文本中启发式抽取候选记忆。对齐 PRD 8.4 的 Candidate Memory 阶段。

不调用 LLM：用关键词规则识别「用户偏好 / 架构决策 / 历史结论 / 项目事实」
四类陈述。抽取结果必须经过用户确认才能入库（本模块只产出候选，不写库）。
"""

import re
from dataclasses import dataclass

from context_pilot.memory.models import MemoryType

# 触发词 → 记忆类型。按优先级排列，先命中先归类。
# 架构约束优先于用户偏好："必须 X，禁止 Y" 整体是架构决策而非个人偏好。
_RULES: tuple[tuple[tuple[str, ...], MemoryType], ...] = (
    (("必须", "应当", "应该", "需要", "always", "must", "should"), MemoryType.ARCHITECTURE_DECISION),
    (("不要", "别用", "禁止", "拒绝", "别再", "avoid", "never"), MemoryType.USER_PREFERENCE),
    (("决定", "结论", "选定", "最终", "采用", "decided", "decision"), MemoryType.HISTORICAL_DECISION),
)

_KNOWN_FACTS = (
    "使用",
    "基于",
    "依赖",
    "采用",
    "运行在",
    "目标是",
)

_MIN_LENGTH = 6


@dataclass(frozen=True)
class CandidateMemory:
    """一条待用户确认的记忆候选。"""

    type: MemoryType
    content: str


def _classify(sentence: str) -> MemoryType | None:
    lowered = sentence.lower()
    for keywords, memory_type in _RULES:
        if any(keyword in lowered for keyword in keywords):
            return memory_type
    if any(fact in lowered for fact in _KNOWN_FACTS):
        return MemoryType.PROJECT_FACT
    return None


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"[。！？!?\n]+", text) if s.strip()]


def extract(text: str) -> list[CandidateMemory]:
    """从一段对话/文本中抽取候选记忆，按出现顺序返回。"""
    candidates: list[CandidateMemory] = []
    for sentence in _split_sentences(text):
        if len(sentence) < _MIN_LENGTH:
            continue
        memory_type = _classify(sentence)
        if memory_type is None:
            continue
        candidates.append(CandidateMemory(memory_type, sentence))
    return candidates


def find_conflicts(
    existing: list[str], candidate_content: str, threshold: float = 0.5
) -> list[str]:
    """用简单共现相似度检测候选记忆与已有记忆的冲突/重复。

    基于词集合的 Jaccard 相似度（纯启发式，无依赖）。返回相似度超阈值
    的已有记忆原文，供确认界面提示。
    """

    def tokens(text: str) -> set[str]:
        return set(re.findall(r"[A-Za-z0-9_一-鿿]+", text.lower()))

    candidate_tokens = tokens(candidate_content)
    if not candidate_tokens:
        return []
    return [
        existing
        for existing in existing
        if _jaccard(candidate_tokens, tokens(existing)) >= threshold
    ]


def _jaccard(a: set[str], b: set[str]) -> float:
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)
