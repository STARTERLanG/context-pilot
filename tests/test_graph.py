"""Code Graph 单测。"""

import tempfile
from pathlib import Path

from context_pilot.graph.builder import CodeGraphBuilder
from context_pilot.graph.models import GraphEdge
from context_pilot.graph.retriever import GraphRetriever
from context_pilot.graph.store import GraphStore
from context_pilot.project.models import ProjectContext


def _build(tmp_path):
    (tmp_path / "order.py").write_text(
        "class OrderService:\n    def refund(self):\n        pass\n", encoding="utf-8"
    )
    (tmp_path / "refund.py").write_text(
        "class RefundService:\n    pass\n", encoding="utf-8"
    )
    (tmp_path / "special.py").write_text(
        "class SpecialOrder(OrderService):\n    pass\n", encoding="utf-8"
    )
    symbols, edges = CodeGraphBuilder().build(tmp_path)
    return symbols, edges


def test_builder_extracts_symbols(tmp_path):
    symbols, _ = _build(tmp_path)
    names = {s.name for s in symbols}
    assert "OrderService" in names
    assert "refund" in names
    assert "RefundService" in names


def test_builder_extracts_inheritance_edge(tmp_path):
    _, edges = _build(tmp_path)
    inherits = [e for e in edges if e.relation == "inherits"]
    assert GraphEdge("SpecialOrder", "OrderService", "inherits") in inherits


def test_store_roundtrip(tmp_path):
    symbols, edges = _build(tmp_path)
    store = GraphStore(tmp_path / "graph.db")
    store.replace_all(symbols, edges)

    neighbors = store.neighbors("SpecialOrder")
    assert len(neighbors) == 1
    assert neighbors[0].target == "OrderService"


def test_graph_retriever_expands_inheritance(tmp_path):
    symbols, edges = _build(tmp_path)
    store = GraphStore(tmp_path / "graph.db")
    store.replace_all(symbols, edges)

    # 查询命中 SpecialOrder，图扩展应带出 OrderService 所在文件
    results = GraphRetriever(store).search("SpecialOrder", ProjectContext(root=tmp_path.resolve()))

    assert results
    assert any("order.py" in item.source for item in results)
    assert any("图扩展" in item.reason for item in results)
