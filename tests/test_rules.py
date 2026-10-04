"""规则加载与匹配单测。"""

from context_pilot.rules.loader import load
from context_pilot.rules.matcher import select
from context_pilot.rules.models import Activation, Rule


def test_load_reads_tiered_rule_files_with_priority(tmp_path):
    (tmp_path / "AGENTS.md").write_text("一级规则", encoding="utf-8")
    (tmp_path / "README.md").write_text("项目说明", encoding="utf-8")

    rules = {rule.source: rule for rule in load(tmp_path)}

    assert "AGENTS.md" in rules
    assert "README.md" in rules
    assert rules["AGENTS.md"].priority > rules["README.md"].priority


def test_load_ignores_empty_file(tmp_path):
    (tmp_path / "AGENTS.md").write_text("   \n", encoding="utf-8")
    assert load(tmp_path) == []


def test_load_reads_rule_directory(tmp_path):
    rules_dir = tmp_path / ".cursor" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "style.md").write_text("风格约定", encoding="utf-8")

    sources = [rule.source for rule in load(tmp_path)]

    assert any("style.md" in source for source in sources)


def test_select_keeps_always_and_sorts_by_priority():
    low = Rule(source="a.md", content="a", priority=50)
    high = Rule(source="b.md", content="b", priority=100)
    manual = Rule(source="c.md", content="c", activation=Activation.MANUAL)

    selected = select([low, high, manual])

    assert [rule.source for rule in selected] == ["b.md", "a.md"]
