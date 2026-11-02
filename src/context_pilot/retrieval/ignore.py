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
#
# 判定由 is_sensitive() 统一执行（前缀匹配 或 子串包含），因此这里写
# "credential" 而非 "credentials." —— 后者要求带点，会让名为 `credentials`
#（无扩展名）的文件漏网，而这恰恰是常见命名。
#
# 权衡：宁可少读一个可能相关的普通文件，也不放一个凭据进 LLM 上下文，
# 所以像 "secret" 这类词即便存在 "secretary.py" 式误伤的可能也保留。
SENSITIVE_PATTERNS: tuple[str, ...] = (
    # 环境变量 / 工具配置：常内含密钥或 Token
    ".env",
    ".npmrc",
    ".yarnrc",
    ".netrc",
    ".dockercfg",
    ".htpasswd",
    # 私钥与证书容器
    ".pem",
    ".key",
    ".pfx",
    ".p12",
    ".jks",
    ".keystore",
    ".ppk",
    ".kdbx",
    ".gpg",
    ".asc",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    # 命名直指凭据
    "credential",
    "secret",
    "private_key",
    "service-account",
    "service_account",
    "token.json",
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
