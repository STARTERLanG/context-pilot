"""ripgrep 检索器单测。rg 不可用时跳过（环境依赖）。"""

import shutil
from pathlib import Path

import pytest

from context_pilot.project.models import ProjectContext
from context_pilot.retrieval.base import Retriever
from context_pilot.retrieval.ripgrep import RipgrepRetriever, RipgrepUnavailable

pytestmark = pytest.mark.skipif(
    shutil.which("rg") is None and not Path(
        Path.home()
        / "AppData/Local/Microsoft/WinGet/Packages"
        / "BurntSushi.ripgrep.MSVC_Microsoft.Winget.Source_8wekyb3d8bbwe"
    ).exists(),
    reason="rg 未安装",
)


def test_constructor_raises_when_missing(monkeypatch):
    monkeypatch.setattr("context_pilot.retrieval.ripgrep._find_rg", lambda: None)
    with pytest.raises(RipgrepUnavailable):
        RipgrepRetriever()


def test_search_finds_files_and_relative_paths(tmp_path):
    (tmp_path / "app.py").write_text("def handle_order(): pass\n", encoding="utf-8")
    (tmp_path / "other.py").write_text("unrelated\n", encoding="utf-8")

    project = ProjectContext(root=tmp_path.resolve())
    results = RipgrepRetriever().search("handle_order", project)

    sources = [item.source for item in results]
    assert "app.py" in sources
    assert not any(source.startswith(str(tmp_path.resolve())) for source in sources)
    assert any("handle_order" in item.content for item in results)


def test_search_chinese_substring(tmp_path):
    (tmp_path / "note.md").write_text("修一下订单接口 加个退款功能\n", encoding="utf-8")

    project = ProjectContext(root=tmp_path.resolve())
    results = RipgrepRetriever().search("退款功能", project)

    assert any("note.md" == item.source for item in results)


def test_search_respects_ignored_dirs(tmp_path):
    (tmp_path / "app.py").write_text("OrderService\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "lib.js").write_text("OrderService\n", encoding="utf-8")

    project = ProjectContext(root=tmp_path.resolve())
    sources = [item.source for item in RipgrepRetriever().search("OrderService", project)]

    assert "app.py" in sources
    assert not any("node_modules" in source for source in sources)


def test_retriever_satisfies_protocol(tmp_path):
    assert isinstance(RipgrepRetriever(), Retriever)
