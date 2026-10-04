"""Token 数量的近似估算。

不引入分词器依赖：本项目面向任意 OpenAI 兼容端点，没有统一的分词器。
日文/中文字符按 1 token 计，其余按约 4 字符 1 token，这是业界常用的粗略换算。
仅用于 UI 展示（PRD 10.3）与预算提示，不用于精确计费。
"""

_CJK_RANGES = (
    (0x3000, 0x303F),   # CJK 标点
    (0x3040, 0x30FF),   # 日文假名
    (0x4E00, 0x9FFF),   # CJK 统一表意
    (0xAC00, 0xD7AF),   # 韩文
    (0xFF00, 0xFFEF),   # 全角字符
)

_CHARS_PER_TOKEN = 4


def _is_wide(char: str) -> bool:
    code = ord(char)
    return any(low <= code <= high for low, high in _CJK_RANGES)


def estimate(text: str) -> int:
    """估算文本的 token 数。空文本为 0。"""
    if not text:
        return 0

    wide = sum(1 for char in text if _is_wide(char))
    narrow = len(text) - wide
    return wide + (narrow + _CHARS_PER_TOKEN - 1) // _CHARS_PER_TOKEN
