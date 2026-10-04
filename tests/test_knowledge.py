"""项目知识摘要单测。"""

from context_pilot.project.knowledge import summarize
from context_pilot.project.models import ProjectContext


def test_summarize_includes_basic_info(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (tmp_path / "uv.lock").write_text("", encoding="utf-8")
    (tmp_path / "src" / "app").mkdir(parents=True)
    (tmp_path / "src" / "app" / "main.py").write_text("def main(): pass\n", encoding="utf-8")

    project = ProjectContext(root=tmp_path.resolve(), languages=("python",), package_manager="uv")
    summary = summarize(project)

    assert "python" in summary
    assert "uv" in summary
    assert "src/" in summary
    assert "main.py" in summary


def test_summarize_ignores_noise_dirs(tmp_path):
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "x.js").write_text("x", encoding="utf-8")
    (tmp_path / "app.py").write_text("pass\n", encoding="utf-8")

    project = ProjectContext(root=tmp_path.resolve())
    summary = summarize(project)

    assert "node_modules" not in summary
    assert "app.py" in summary
