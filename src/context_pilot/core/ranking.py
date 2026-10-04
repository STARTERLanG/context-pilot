"""上下文排序。对齐 PRD 7.3：权重配置化，不硬编码。

本轮只有「检索相关度」一个信号可用（来自 KeywordRetriever）。
semantic / symbol / explicit_reference 三个维度在对应检索能力落地后再接入，
权重字段已预留，接入时只需在 _signal 里补一行，不改变调用方。
"""

from dataclasses import dataclass

from context_pilot.core.models import ContextItem

# PRD 7.3 的默认权重
_DEFAULT_SEMANTIC = 0.35
_DEFAULT_PATH = 0.15
_DEFAULT_SYMBOL = 0.20
_DEFAULT_RULE_PRIORITY = 0.15
_DEFAULT_EXPLICIT_REFERENCE = 0.15


@dataclass(frozen=True)
class RankingWeights:
    semantic: float = _DEFAULT_SEMANTIC
    path: float = _DEFAULT_PATH
    symbol: float = _DEFAULT_SYMBOL
    rule_priority: float = _DEFAULT_RULE_PRIORITY
    explicit_reference: float = _DEFAULT_EXPLICIT_REFERENCE


def _normalize(values: list[float]) -> list[float]:
    """min-max 归一化到 [0,1]；全部相等时返回全 0，避免除零。"""
    if not values:
        return []
    low, high = min(values), max(values)
    if high == low:
        return [0.0] * len(values)
    return [(v - low) / (high - low) for v in values]


def rank(
    items: list[ContextItem], weights: RankingWeights | None = None
) -> list[ContextItem]:
    """按加权分数降序排列上下文项。"""
    if not items:
        return []

    weights = weights or RankingWeights()
    relevance_norm = _normalize([item.relevance for item in items])

    scored: list[tuple[float, ContextItem]] = []
    for item, relevance in zip(items, relevance_norm, strict=True):
        score = relevance * (weights.path + weights.semantic + weights.symbol)
        if item.type == "rule":
            score += (item.priority / 100.0) * weights.rule_priority
        scored.append((score, item))

    # 分数降序；分数相同时按来源升序，保证结果可复现（两次排序利用稳定排序）
    scored.sort(key=lambda pair: pair[1].source)
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored]
