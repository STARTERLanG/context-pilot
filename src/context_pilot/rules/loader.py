"""从项目中的规则文件加载规则。对齐 PRD 6.2 的文件清单。

本轮把每个规则文件整体视为一条 ALWAYS 规则；按标题拆分、解析 file-match 模式
留待后续（需要先定义各 Agent 的规则格式）。
"""

from pathlib import Path

from context_pilot.rules.models import Activation, Rule

# 文件清单 → 优先级。一级规则优先于二级，文档最低。
_TIERS: tuple[tuple[tuple[str, ...], int], ...] = (
    (
        ("AGENTS.md", "AGENTS.local.md", "CLAUDE.md", "GEMINI.md", "CODEX.md"),
        100,
    ),
    (
        (".github/copilot-instructions.md",),
        80,
    ),
    (
        ("README.md", "CONTRIBUTING.md", "ARCHITECTURE.md"),
        50,
    ),
)

# 二级规则：目录下所有 .md 都加载
_RULE_DIRS: tuple[str, ...] = (".cursor/rules", ".qoder/rules", ".github/instructions")

_MAX_RULE_CHARS = 4000  # 单条规则截断上限，防止整份大文档撑爆上下文


def _read(path: Path, root: Path, priority: int) -> Rule | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    if not text:
        return None
    return Rule(
        source=str(path.relative_to(root)),
        content=text[:_MAX_RULE_CHARS],
        activation=Activation.ALWAYS,
        priority=priority,
        path=path,
    )


def load(root: Path) -> list[Rule]:
    """加载 root 下的规则文件，返回去重后的规则列表。"""
    root = root.resolve()
    rules: list[Rule] = []
    seen: set[Path] = set()

    for names, priority in _TIERS:
        for name in names:
            path = root / name
            if path.is_file() and path not in seen:
                rule = _read(path, root, priority)
                if rule is not None:
                    rules.append(rule)
                    seen.add(path)

    for directory in _RULE_DIRS:
        dir_path = root / directory
        if not dir_path.is_dir():
            continue
        for path in sorted(dir_path.rglob("*.md")):
            if path.is_file() and path not in seen:
                rule = _read(path, root, 80)
                if rule is not None:
                    rules.append(rule)
                    seen.add(path)

    return rules
