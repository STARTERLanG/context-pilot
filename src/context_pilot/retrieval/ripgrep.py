"""基于 ripgrep 的检索器（PRD 6.5 Level 1 关键词检索）。

与 KeywordRetriever 实现相同协议，可互换。rg 比纯 Python 遍历快一个数量级，
适合大仓库。rg 不可用时在实例化时显式抛出，由调用方决定回退策略。
"""

import os
import re
import shutil
import subprocess
from pathlib import Path, PurePath

from context_pilot.core.models import ContextItem
from context_pilot.project.models import ProjectContext
from context_pilot.retrieval.ignore import (
    IGNORED_DIRS,
    is_sensitive,
    is_text_candidate,
)
from context_pilot.retrieval.snippet import extract_snippet

_MAX_RESULTS = 20
_MAX_ITEM_CHARS = 4000

_CN_RE = re.compile(r"[一-鿿]+")
_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
# 匹配 "path:行号:内容"：路径（贪婪，含 Windows 盘符冒号）+ 纯数字行号 + 内容（可含冒号）
_LINE_RE = re.compile(r"^(.*):(\d+):(.*)$")


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
            "--ignore-case",
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

        # 每条命中的行号（1 起），用于提取精确片段；同时统计每个文件的命中数
        # 过滤放在解析之后、建条目之前：rg 只负责找得快，安全问题一律交给
        # ignore 模块的统一判定（此前这里漏了敏感过滤，而本检索器是默认首选，
        # 导致装了 rg 的机器上 .env 会绕进上下文）。
        hits = [hit for hit in self._parse(output) if self._is_allowed(hit[0])]
        hits.sort(key=lambda pair: pair[1], reverse=True)
        return [
            self._build_item(self._relativize(rel, project.root), count, line_numbers, project)
            for rel, count, line_numbers in hits[: self._max_results]
        ]

    @staticmethod
    def _is_allowed(rel: str) -> bool:
        """是否允许该文件进入上下文：排除敏感文件与非文本文件。"""
        path = PurePath(rel)
        return not is_sensitive(path) and is_text_candidate(path)

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

    def _parse(self, output: str) -> list[tuple[str, int, list[int]]]:
        """解析 'path:line:content' 输出为 (路径, 命中数, 命中行号列表)。

        Windows 路径含盘符冒号，内容也可能含冒号，故用正则定位行号分隔：
        ``^(.*):(\\d+):(.*)$`` —— 贪婪的 ``.*`` 吃掉路径，``\\d+`` 是行号。
        同一文件可能多次出现，按文件聚合命中数（行号去重）。
        """
        counts: dict[str, list[int]] = {}
        for line in output.splitlines():
            match = _LINE_RE.match(line)
            if not match:
                continue
            path_str, line_part, _content = match.groups()
            rel = Path(path_str).as_posix()
            counts.setdefault(rel, []).append(int(line_part))
        return [
            (rel, len(lines), sorted(set(lines)))
            for rel, lines in counts.items()
        ]

    def _relativize(self, path_str: str, root: Path) -> str:
        """把 rg 输出的绝对路径转成项目相对路径；根外文件保持原样。"""
        try:
            return Path(path_str).resolve().relative_to(root).as_posix()
        except ValueError:
            return path_str

    def _build_item(
        self, rel: str, count: int, line_numbers: list[int], project: ProjectContext
    ) -> ContextItem:
        path = project.root / rel
        content = ""
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            content = ""
        snippet, start, end = extract_snippet(content, line_numbers)
        return ContextItem(
            id=rel,
            type="code",
            source=rel,
            path=rel,
            content=content[:_MAX_ITEM_CHARS],
            relevance=float(count),
            reason=f"ripgrep 命中 {count} 处",
            snippet=snippet,
            line_start=start,
            line_end=end,
        )
