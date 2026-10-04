"""项目上下文的数据结构。"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectContext:
    """一次增强所针对的项目根与其识别出的元信息。"""

    root: Path
    git_root: Path | None = None
    languages: tuple[str, ...] = ()
    package_manager: str | None = None
