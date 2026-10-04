"""识别项目根、语言与包管理器。最简实现：只依赖 pathlib，不调用外部命令。"""

from pathlib import Path

from context_pilot.project.models import ProjectContext

# 标记文件 → 语言/包管理器
_LANGUAGE_MARKERS: tuple[tuple[str, str], ...] = (
    ("pyproject.toml", "python"),
    ("setup.py", "python"),
    ("Cargo.toml", "rust"),
    ("package.json", "typescript"),
    ("go.mod", "go"),
)

_PACKAGE_MANAGER_MARKERS: tuple[tuple[str, str], ...] = (
    ("uv.lock", "uv"),
    ("poetry.lock", "poetry"),
    ("Pipfile.lock", "pipenv"),
    ("pnpm-lock.yaml", "pnpm"),
    ("yarn.lock", "yarn"),
    ("package-lock.json", "npm"),
    ("Cargo.lock", "cargo"),
)


def _find_git_root(start: Path) -> Path | None:
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def scan(start: Path) -> ProjectContext:
    """从 start 向上寻找 git 根作为项目根，并在该目录识别语言与包管理器。"""
    start = start.resolve()
    git_root = _find_git_root(start)
    root = git_root or start

    languages = [lang for marker, lang in _LANGUAGE_MARKERS if (root / marker).exists()]
    package_manager = next(
        (mgr for marker, mgr in _PACKAGE_MANAGER_MARKERS if (root / marker).exists()),
        None,
    )

    return ProjectContext(
        root=root,
        git_root=git_root,
        languages=tuple(dict.fromkeys(languages)),
        package_manager=package_manager,
    )
