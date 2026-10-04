"""Token 估算单测。"""

from context_pilot.core.tokens import estimate


def test_empty_is_zero():
    assert estimate("") == 0


def test_ascii_roughly_4_chars_per_token():
    assert estimate("abcd") == 1
    assert estimate("abcdefgh") == 2


def test_wide_chars_count_one_token_each():
    assert estimate("中文") == 2
    assert estimate("测试预算") == 4


def test_mixed_text():
    # 4 个汉字 = 4 token；8 个 ASCII = 2 token
    assert estimate("中文abcd中文abcd") == 6


def test_rounds_up_partial_token():
    assert estimate("abc") == 1  # 3 字符不足 4，按 1 token
