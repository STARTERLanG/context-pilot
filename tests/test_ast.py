"""AST 符号检索单测。"""

from context_pilot.project.models import ProjectContext
from context_pilot.retrieval.ast import AstRetriever


def _project(tmp_path) -> ProjectContext:
    return ProjectContext(root=tmp_path.resolve())


def test_extracts_class_and_function_symbols(tmp_path):
    (tmp_path / "order.py").write_text(
        "class OrderService:\n    def refund(self):\n        pass\n", encoding="utf-8"
    )
    project = _project(tmp_path)

    results = AstRetriever().search("refund OrderService", project)

    assert results
    assert any("OrderService" in item.reason for item in results)
    assert results[0].type == "symbol"


def test_returns_nothing_for_unknown_symbol(tmp_path):
    (tmp_path / "order.py").write_text("class OrderService:\n    pass\n", encoding="utf-8")
    project = _project(tmp_path)

    assert AstRetriever().search("nonexistent_symbol_xyz", project) == []


def test_ignores_non_python_files(tmp_path):
    (tmp_path / "app.ts").write_text("class OrderService {}", encoding="utf-8")
    project = _project(tmp_path)

    assert AstRetriever().search("OrderService", project) == []


def test_respects_ignored_dirs(tmp_path):
    (tmp_path / "order.py").write_text("class OrderService:\n    pass\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "x.py").write_text("class OrderService:\n    pass\n", encoding="utf-8")
    project = _project(tmp_path)

    sources = [item.source for item in AstRetriever().search("OrderService", project)]
    assert not any("node_modules" in source for source in sources)
