"""上下文排序单测。"""

from context_pilot.core.models import ContextItem
from context_pilot.core.ranking import RankingWeights, rank


def _code(source: str, relevance: float) -> ContextItem:
    return ContextItem(id=source, type="code", source=source, content="", relevance=relevance)


def test_rank_orders_by_relevance_descending():
    items = [_code("a.py", 1.0), _code("b.py", 9.0), _code("c.py", 5.0)]

    ranked = rank(items)

    assert [i.source for i in ranked] == ["b.py", "c.py", "a.py"]


def test_rank_is_stable_for_equal_scores():
    items = [_code("b.py", 5.0), _code("a.py", 5.0)]

    ranked = rank(items)

    assert [i.source for i in ranked] == ["a.py", "b.py"]


def test_rank_empty_returns_empty():
    assert rank([]) == []


def test_rank_accepts_custom_weights():
    items = [_code("a.py", 1.0), _code("b.py", 2.0)]
    ranked = rank(items, RankingWeights(semantic=1.0, path=0.0, symbol=0.0))
    assert [i.source for i in ranked] == ["b.py", "a.py"]
