"""检索器单测。"""

from context_pilot.project.models import ProjectContext
from context_pilot.retrieval.keyword import KeywordRetriever, extract_tokens
from context_pilot.retrieval.base import Retriever


def _project(tmp_path) -> ProjectContext:
    return ProjectContext(root=tmp_path.resolve())


def test_extract_tokens_filters_short_words():
    assert extract_tokens("修一下 OrderService 接口 api") == ["orderservice", "api"]


def test_search_ranks_filename_match_above_content_match(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "order.py").write_text("def handle(): pass\n", encoding="utf-8")
    (src / "other.py").write_text("order order order\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "order.py").write_text("order\n", encoding="utf-8")

    results = KeywordRetriever().search("order", _project(tmp_path))
    sources = [item.source for item in results]

    # 文件名命中排第一；node_modules 被忽略
    assert sources[0].endswith("order.py")
    assert not any("node_modules" in s for s in sources)


def test_search_ignores_sensitive_files(tmp_path):
    (tmp_path / ".env").write_text("SECRET=order\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("order\n", encoding="utf-8")

    sources = [i.source for i in KeywordRetriever().search("order", _project(tmp_path))]

    assert ".env" not in sources
    assert "app.py" in sources


def test_search_returns_empty_for_pure_chinese_query(tmp_path):
    (tmp_path / "app.py").write_text("order\n", encoding="utf-8")
    assert KeywordRetriever().search("修一下订单接口", _project(tmp_path)) == []


def test_keyword_retriever_satisfies_protocol():
    assert isinstance(KeywordRetriever(), Retriever)
