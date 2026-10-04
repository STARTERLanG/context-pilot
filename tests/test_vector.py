"""向量检索单测。"""

from context_pilot.project.models import ProjectContext
from context_pilot.retrieval.base import Retriever
from context_pilot.retrieval.vector import VectorRetriever, _cosine


def test_cosine_identical_is_one():
    features = [1, 2, 3]
    assert _cosine(features, features) == 1.0 or abs(_cosine(features, features) - 1.0) < 1e-6


def test_cosine_disjoint_is_zero():
    assert _cosine([1, 2], [3, 4]) == 0.0


def test_cosine_empty_is_zero():
    assert _cosine([], [1, 2]) == 0.0


def test_search_ranks_semantically_similar_file_first(tmp_path):
    # n-gram 哈希只能做「文本相似」的近似语义，跨语言命中需真实 Embedding
    # 此处验证：与查询共享更多词元的文件排在前面
    (tmp_path / "order_service.py").write_text(
        "def handle_order(service):\n    return service.process()\n", encoding="utf-8"
    )
    (tmp_path / "other.py").write_text("def unrelated_math_helper(): pass\n", encoding="utf-8")
    project = ProjectContext(root=tmp_path.resolve())

    results = VectorRetriever().search("order service process", project)

    assert results
    assert results[0].source == "order_service.py"


def test_search_returns_empty_for_short_query(tmp_path):
    (tmp_path / "a.py").write_text("class X:\n    pass\n", encoding="utf-8")
    project = ProjectContext(root=tmp_path.resolve())
    assert VectorRetriever().search("a", project) == []


def test_retriever_satisfies_protocol(tmp_path):
    assert isinstance(VectorRetriever(), Retriever)
