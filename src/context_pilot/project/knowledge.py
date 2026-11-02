"""项目知识摘要（PRD 42 Phase 9：Project Knowledge）。

从已识别的元信息生成一段「项目地图」，作为上下文注入增强过程。
纯生成逻辑，无外部依赖。
"""

from pathlib import Path

from context_pilot.project.models import ProjectContext
from context_pilot.retrieval.ignore import IGNORED_DIRS


def summarize(project: ProjectContext, max_depth: int = 3, max_entries: int = 40) -> str:
    """生成项目知识摘要文本。"""
    lines: list[str] = []
    lines.append(f"项目根目录：{project.root}")
    if project.languages:
        lines.append(f"语言：{'、'.join(project.languages)}")
    if project.package_manager:
        lines.append(f"包管理器：{project.package_manager}")
    if project.git_root is not None:
        lines.append(f"Git 根：{project.git_root}")

    structure = _structure_lines(project.root, project.root, max_depth, max_entries)
    if structure:
        lines.append("模块结构：")
        lines.extend(structure)

    return "\n".join(lines)


def _structure_lines(
    root: Path, current: Path, max_depth: int, max_entries: int
) -> list[str]:
    """返回目录树的关键行（跳过常见噪音目录）。

    忽略名单复用 retrieval.ignore：此前这里手抄了一份且少了 target /
    .mypy_cache，与索引器和检索器判定不一致（同一目录在三处表现不同）。
    """
    ignored = IGNORED_DIRS
    depth = len(current.relative_to(root).parts) if current != root else 0
    if depth > max_depth:
        return []

    lines: list[str] = []
    entries: list[Path] = []
    try:
        entries = sorted(
            [p for p in current.iterdir() if not p.name.startswith(".")],
            key=lambda p: (p.is_file(), p.name.lower()),
        )
    except OSError:
        return []

    for entry in entries:
        if len(lines) >= max_entries:
            break
        if entry.is_dir():
            if entry.name in ignored:
                continue
            indent = "  " * depth
            lines.append(f"{indent}{entry.name}/")
            lines.extend(_structure_lines(root, entry, max_depth, max_entries))
        else:
            if entry.suffix in (".pyc", ".pyo"):
                continue
            indent = "  " * depth
            lines.append(f"{indent}{entry.name}")
    return lines
