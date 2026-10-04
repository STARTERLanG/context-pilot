"""Diff 计算单测。"""

from context_pilot.core.diff import KIND_ADDED, KIND_REMOVED, KIND_UNCHANGED, compare


def test_identical_text_all_unchanged():
    lines = compare("同一行", "同一行")
    assert all(line.kind == KIND_UNCHANGED for line in lines)
    assert len(lines) == 1


def test_addition_detected():
    lines = compare("第一行", "第一行\n新增行")
    kinds = [line.kind for line in lines]
    assert KIND_UNCHANGED in kinds
    assert KIND_ADDED in kinds
    added = next(line for line in lines if line.kind == KIND_ADDED)
    assert added.text == "新增行"
    assert added.old_line is None
    assert added.new_line == 2


def test_removal_detected():
    lines = compare("被删行\n保留行", "保留行")
    kinds = [line.kind for line in lines]
    assert KIND_REMOVED in kinds
    removed = next(line for line in lines if line.kind == KIND_REMOVED)
    assert removed.text == "被删行"
    assert removed.new_line is None
    assert removed.old_line == 1


def test_line_numbers_assigned():
    lines = compare("a\nb\nc", "a\nx\nc")
    with_numbers = [line for line in lines if line.old_line is not None]
    assert with_numbers  # 至少存在带行号的行
