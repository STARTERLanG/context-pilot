"""热键解析单测。"""

import pytest

from context_pilot.platform.keys import (
    HotkeyParseError,
    format,
    is_valid,
    parse,
)


def test_parse_ctrl_shift_e():
    modifiers, vk = parse("ctrl+shift+e")
    assert modifiers == 0x0002 | 0x0004
    assert vk == ord("E")


def test_parse_is_case_insensitive_and_trims():
    assert parse("Ctrl + Alt + K") == parse("ctrl+alt+k")


def test_parse_function_key():
    _, vk = parse("ctrl+f5")
    assert vk == 0x74  # F5


def test_parse_requires_modifier():
    with pytest.raises(HotkeyParseError, match="修饰键"):
        parse("e")


def test_parse_rejects_unknown_key():
    with pytest.raises(HotkeyParseError, match="无法识别"):
        parse("ctrl+不存在的键")


def test_parse_rejects_modifier_as_main_key():
    with pytest.raises(HotkeyParseError, match="主键不能是修饰键"):
        parse("ctrl+shift")


def test_format_roundtrip():
    modifiers, vk = parse("ctrl+alt+p")
    assert format(modifiers, vk) == "ctrl+alt+p"


def test_format_function_key():
    modifiers, vk = parse("ctrl+f12")
    assert format(modifiers, vk) == "ctrl+f12"


def test_is_valid():
    assert is_valid("ctrl+shift+e") is True
    assert is_valid("e") is False
    assert is_valid("ctrl+nonsense") is False
