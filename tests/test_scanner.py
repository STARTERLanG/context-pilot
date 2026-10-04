"""项目扫描单测。"""

from context_pilot.project.scanner import scan


def test_scan_detects_python_and_uv(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (tmp_path / "uv.lock").write_text("", encoding="utf-8")

    result = scan(tmp_path)

    assert result.root == tmp_path.resolve()
    assert "python" in result.languages
    assert result.package_manager == "uv"


def test_scan_finds_git_root_from_nested_dir(tmp_path):
    (tmp_path / ".git").mkdir()
    nested = tmp_path / "src" / "deep"
    nested.mkdir(parents=True)

    result = scan(nested)

    assert result.root == tmp_path.resolve()
    assert result.git_root == tmp_path.resolve()
