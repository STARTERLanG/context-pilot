"""检索时忽略的目录与文件。对齐 PRD 33 的敏感文件与构建产物排除项。"""

from pathlib import PurePath

IGNORED_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        "node_modules",
        "dist",
        "build",
        "venv",
        ".venv",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".idea",
        ".vscode",
        "target",
    }
)

# 敏感文件：禁止进入上下文（安全红线）
SENSITIVE_PATTERNS: tuple[str, ...] = (
    ".env",
    ".env.",
    ".pem",
    ".key",
    "credentials.",
    "secrets.",
)

# 只看文本类源码/文档，避免读二进制
TEXT_SUFFIXES: frozenset[str] = frozenset(
    {
        ".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".vue", ".go", ".rs", ".java",
        ".kt", ".rb", ".php", ".c", ".h", ".cpp", ".hpp", ".cs", ".swift", ".scala",
        ".sql", ".sh", ".ps1", ".toml", ".yaml", ".yml", ".json", ".ini", ".cfg",
        ".md", ".txt", ".qml",
    }
)

_MAX_FILE_BYTES = 512 * 1024  # 超过此大小的文件不读，避免拖慢与爆上下文


def is_ignored_dir(name: str) -> bool:
    return name in IGNORED_DIRS


def is_sensitive(path: PurePath) -> bool:
    name = path.name.lower()
    return any(name.startswith(pat) or pat in name for pat in SENSITIVE_PATTERNS)


def is_text_candidate(path: PurePath) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES
