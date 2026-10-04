"""基于 ripgrep 的检索器（PRD 6.5 Level 1 关键词检索）。

与 KeywordRetriever 实现相同协议，可互换。rg 比纯 Python 遍历快一个数量级，
适合大仓库。rg 不可用时在实例化时显式抛出，由调用方决定回退策略。
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

from context_pilot.core.models import ContextItem
from context_pilot.project.models import ProjectContext
from context_pilot.retrieval.ignore import (
    IGNORED_DIRS,
    SENSITIVE_PATTERNS,
    TEXT_SUFFIXES,
)

_MAX_RESULTS = 20
_MAX_ITEM_CHARS = 4000
_MAX_MATCH_COUNT = 20  # 单个文件内最多记录命中次数，避免 grep 输出过大

_CN_RE = re.compile(r"[一-鿿]+")
_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class RipgrepUnavailable(RuntimeError):
    """rg 二进制不存在。"""


def _find_rg() -> str | None:
    """定位 rg 二进制：先找 PATH，再找常见安装位置。"""
    found = shutil.which("rg")
    if found:
        return found

    local = os.environ.get("LOCALAPPDATA", "")
    winget_dir = os.path.join(
        local,
        "Microsoft", "WinGet", "Packages",
        "BurntSushi.ripgrep.MSVC_Microsoft.Winget.Source_8wekyb3d8bbwe",
    )
    if os.path.isdir(winget_dir):
        candidates = sorted(os.listdir(winget_dir))
        for name in reversed(candidates):  # 版本号升序，取最新
            exe = os.path.join(winget_dir, name, "rg.exe")
            if os.path.isfile(exe):
                return exe
    return None


def _build_ignore_args() -> list[str]:
    """生成排除目录的 glob。用 **/ 匹配任意层级，避免目录不在搜索起点时失效。"""
    args = []
    for directory in sorted(IGNORED_DIRS):
        args += ["--glob", f"!**/{directory}/**"]
    return args


class RipgrepRetriever:
    """调用 rg 检索文件路径与内容，按命中行数排序。"""

    def __init__(self, max_results: int = _MAX_RESULTS) -> None:
        self._rg = _find_rg()
        if self._rg is None:
            raise RipgrepUnavailable("未找到 ripgrep，请安装或改用 KeywordRetriever")
        self._max_results = max_results

    def search(self, query: str, project: ProjectContext) -> list[ContextItem]:
        # 中文关键词直接交给 rg 做子串匹配；标识符词元限定边界
        patterns = self._patterns(query)
        if not patterns:
            return []

        cmd = [
            self._rg, "--no-heading", "--with-filename", "--line-number",
            "--count-matches", "--ignore-case",
        ]
        cmd += self._ignore_args_for(project)
        for pattern in patterns:
            cmd += ["-e", pattern]
        cmd += [str(project.root)]

        try:
            output = subprocess.run(
                cmd, capture_output=True, timeout=30, encoding="utf-8", errors="replace"
            ).stdout
        except (subprocess.TimeoutExpired, OSError):
            return []

        hits = self._parse(output)
        hits.sort(key=lambda pair: pair[1], reverse=True)
        return [
            self._build_item(self._relativize(rel, project.root), count, project)
            for rel, count in hits[: self._max_results]
        ]

    def _patterns(self, query: str) -> list[str]:
        """把查询拆成 rg 模式：中文片段整串匹配，标识符按词匹配。"""
        # 提取连续中文字段（整串子串匹配）
        chinese_blocks = _CN_RE.findall(query)
        identifiers = _TOKEN_RE.findall(query)
        patterns: list[str] = []
        for block in chinese_blocks:
            if len(block) >= 2:
                patterns.append(block)
        for token in identifiers:
            if len(token) >= 3:
                patterns.append(token)  # 大小写不敏感子串，能命中 OrderService 内嵌的 order
        # 去重，最多 8 个模式（rg -e 组合）
        seen: set[str] = set()
        result: list[str] = []
        for pattern in patterns:
            if pattern not in seen:
                seen.add(pattern)
                result.append(pattern)
            if len(result) >= 8:
                break
        return result

    def _ignore_args_for(self, project: ProjectContext) -> list[str]:
        args = _build_ignore_args()
        if project.git_root is not None:
            args += ["--ignore-file", str(project.git_root / ".gitignore")]
        return args

    def _parse(self, output: str) -> list[tuple[str, int]]:
        """解析 'path:count' 输出为 (相对路径, 命中数)。去重（rg 可能多次列出同名）。"""
        counts: dict[str, int] = {}
        for line in output.splitlines():
            if ":" not in line:
                continue
            path_part, _, count_part = line.rpartition(":")
            if not count_part.isdigit():
                continue
            rel = Path(path_part)
            counts[rel.as_posix()] = counts.get(rel.as_posix(), 0) + min(
                int(count_part), _MAX_MATCH_COUNT
            )
        return list(counts.items())

    def _relativize(self, path_str: str, root: Path) -> str:
        """把 rg 输出的绝对路径转成项目相对路径；根外文件保持原样。"""
        try:
            return Path(path_str).resolve().relative_to(root).as_posix()
        except ValueError:
            return path_str

    def _build_item(self, rel: str, count: int, project: ProjectContext) -> ContextItem:
        path = project.root / rel
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            content = ""
        return ContextItem(
            id=rel,
            type="code",
            source=rel,
            path=rel,
            content=content[:_MAX_ITEM_CHARS],
            relevance=float(count),
            reason=f"ripgrep 命中 {count} 处",
        )
