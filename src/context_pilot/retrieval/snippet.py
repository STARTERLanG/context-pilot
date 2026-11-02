"""从文件内容中提取「命中片段」的共享工具。

检索器命中某文件后，不应把整文件塞进上下文，而应只返回真正命中的那几行
（以及少量上下文行），供「上下文检查器」点击文件时精确展示被选中的代码段
（PRD 10.2），也服务于「按需获取最小必要文件集」的上下文预算控制。
"""

from pathlib import Path

# 命中行前后各保留的上下文行数
_CONTEXT_LINES = 2
# 片段最大行数，超过则截断中间
_MAX_SNIPPET_LINES = 40


def extract_snippet(
    text: str, matched_line_numbers: list[int]
) -> tuple[str, int | None, int | None]:
    """从文件全文提取命中的代码片段。

    参数 ``matched_line_numbers`` 为命中的行号（1 起、升序）。返回
    ``(片段文本, 起始行号, 结束行号)``；无命中行时返回空片段与 None 行号。
    """
    if not matched_line_numbers:
        return "", None, None

    lines = text.splitlines()
    total = len(lines)
    if total == 0:
        return "", None, None

    # 归一化行号到 [1, total]，去重排序
    nums = sorted({n for n in matched_line_numbers if 1 <= n <= total})
    if not nums:
        return "", None, None

    # 合并相邻命中区间，扩展到前后 _CONTEXT_LINES 行
    start = max(1, nums[0] - _CONTEXT_LINES)
    end = min(total, nums[-1] + _CONTEXT_LINES)

    selected = lines[start - 1 : end]
    # 控制片段长度：过长则保留首尾，中间用省略号标注
    if len(selected) > _MAX_SNIPPET_LINES:
        head = selected[:_MAX_SNIPPET_LINES // 2]
        tail = selected[-_MAX_SNIPPET_LINES // 2:]
        snippet_lines = head + ["..."] + tail
        # 行号仍以原始 start/end 标注，省略号不代表真实行
    else:
        snippet_lines = selected

    snippet = "\n".join(snippet_lines)
    return snippet, start, end


def find_matching_lines(text: str, patterns: list[str]) -> list[int]:
    """返回 ``text`` 中命中任一 ``patterns``（子串，忽略大小写）的行号列表（1 起）。"""
    lines = text.splitlines()
    lowered_patterns = [p.lower() for p in patterns if p]
    hits: list[int] = []
    for index, line in enumerate(lines, start=1):
        lowered = line.lower()
        if any(p in lowered for p in lowered_patterns):
            hits.append(index)
    return hits


def read_file(path: Path) -> str:
    """安全读取文本文件，失败返回空串。"""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
