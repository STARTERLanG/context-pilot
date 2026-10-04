"""行级文本差异。对齐 PRD 10.1 的 Original vs Enhanced 对比。

用标准库 difflib，输出扁平行列表供 QML 直接渲染，避免在 QML 里做逻辑。
"""

from dataclasses import dataclass
from difflib import SequenceMatcher

KIND_UNCHANGED = "unchanged"
KIND_ADDED = "added"
KIND_REMOVED = "removed"


@dataclass(frozen=True)
class DiffLine:
    """一行差异。old_line/new_line 为对应原文/新文行号，缺失侧为 None。"""

    kind: str
    text: str
    old_line: int | None = None
    new_line: int | None = None


def compare(old_text: str, new_text: str) -> list[DiffLine]:
    """逐行比较，返回扁平的差异行列表。"""
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    matcher = SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)

    result: list[DiffLine] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(i2 - i1):
                result.append(
                    DiffLine(KIND_UNCHANGED, old_lines[i1 + offset], i1 + offset + 1, j1 + offset + 1)
                )
        else:
            for index in range(i1, i2):
                result.append(DiffLine(KIND_REMOVED, old_lines[index], index + 1, None))
            for index in range(j1, j2):
                result.append(DiffLine(KIND_ADDED, new_lines[index], None, index + 1))
    return result
