"""core/shortcuts 与 [shortcuts] 持久化的规则单测。

这份测试锁的是一条硬约束：**除 Esc / F1-F12 外，窗口内快捷键必须是组合键**。
它不是审美偏好，而是这类功能的成败线——单字母键一旦成为快捷键，用户在输入框
里打字的每个字母都会被当成命令（视图乱跳、内容照常输进去）。靠「判断焦点」去
打补丁治不好：换个没被门控的键就复发。所以从规则层禁止，并在这里钉死。
"""

import pytest

from context_pilot.config import load, save
from context_pilot.core.shortcuts import (
    ACTION_IDS,
    NAKED_KEYS,
    SCHEMES,
    canonical,
    describe,
    normalize_bindings,
    normalize_sequence,
    scheme_bindings,
    sequence_error,
    validate_bindings,
    variants,
)


# ---------- 预设方案 ----------
def test_every_scheme_passes_validation():
    """三套预设都不能自带问题——否则用户一进设置页就看到红字。"""
    for scheme in SCHEMES:
        issues = validate_bindings(dict(scheme.bindings))
        assert [i for i in issues if i.level == "error"] == [], scheme.id


def test_every_scheme_binds_every_action():
    for scheme in SCHEMES:
        assert tuple(a for a, _ in scheme.bindings) == ACTION_IDS


def test_scheme_lookup_falls_back_to_default():
    """手改坏 scheme 不能让窗口打不开：未知方案退回默认方案。"""
    assert scheme_bindings("不存在的方案") == scheme_bindings("balanced")


# ---------- 单键禁令（本模块的核心）----------
@pytest.mark.parametrize("key", ["e", "d", "c", "r", "u", "a", "1", "space"])
def test_naked_letter_is_rejected(key):
    assert sequence_error(key)


@pytest.mark.parametrize("key", sorted(NAKED_KEYS))
def test_whitelisted_naked_keys_allowed_when_permitted(key):
    assert sequence_error(key, allow_naked=True) == ""


def test_naked_key_rejected_when_not_permitted():
    """连 Esc 也不行——只有声明了 allow_naked 的动作（close）才能用单键。"""
    assert sequence_error("esc")


@pytest.mark.parametrize("seq", ["ctrl+e", "alt+d", "ctrl+shift+c", "ctrl+enter"])
def test_combos_accepted(seq):
    assert sequence_error(seq) == ""


def test_empty_binding_is_an_error():
    """缺省值必须被当成错误挑出来，而不是静默变成「永不触发」。"""
    assert sequence_error("")


# ---------- 文本编辑保留组合 ----------
@pytest.mark.parametrize("seq", ["ctrl+c", "ctrl+v", "ctrl+x", "ctrl+a", "ctrl+z"])
def test_reserved_edit_combos_rejected(seq):
    """抢走复制/粘贴/撤销是功能性倒退，必须拦在保存之前。"""
    assert sequence_error(seq)


def test_non_reserved_shift_variant_allowed():
    """ctrl+shift+c 未被 Qt 的 TextEdit 占用，不该被误伤。"""
    assert sequence_error("ctrl+shift+c") == ""


# ---------- 重复检测 ----------
def test_duplicate_binding_reported():
    bindings = dict(scheme_bindings("balanced"))
    bindings["rerun"] = bindings["enhance"]
    issues = validate_bindings(bindings)
    assert any(i.level == "error" and "重复" in i.message for i in issues)


def test_enter_and_return_count_as_same_key():
    """Enter 与 Return 是同一个物理键的两种写法，不归一就会漏掉重复。"""
    bindings = dict(scheme_bindings("balanced"))
    bindings["enhance"] = "ctrl+enter"
    bindings["rerun"] = "ctrl+return"
    issues = validate_bindings(bindings)
    assert any(i.level == "error" and "重复" in i.message for i in issues)

    assert canonical("ctrl+return") == canonical("ctrl+enter")


def test_variants_cover_both_enter_spellings():
    assert set(variants("ctrl+enter")) == {"ctrl+enter", "ctrl+return"}
    assert variants("ctrl+e") == ("ctrl+e",)


def test_global_hotkey_collision_is_warning_only():
    """与全局热键相同只是体验瑕疵（会双触发），不该阻断保存。"""
    bindings = dict(scheme_bindings("balanced"))
    issues = validate_bindings(bindings, global_hotkeys=["ctrl+enter"])
    warnings = [i for i in issues if i.level == "warning"]
    assert warnings and not [i for i in issues if i.level == "error"]


# ---------- 规范化与兜底 ----------
def test_normalize_sequence_compacts_spacing():
    assert normalize_sequence(" Ctrl + Enter ") == "ctrl+enter"


def test_normalize_bindings_repairs_broken_config():
    """手改坏 toml / 旧版遗留写法：非法值回退方案默认值，绝不留下裸字母键。"""
    broken = {"enhance": "e", "rerun": "ctrl+c", "use": ""}
    fixed = normalize_bindings(broken, "balanced")
    assert fixed == scheme_bindings("balanced")


def test_normalize_bindings_deduplicates():
    raw = dict(scheme_bindings("balanced"))
    raw["rerun"] = raw["enhance"]
    fixed = normalize_bindings(raw, "balanced")
    seen = [canonical(v) for v in fixed.values()]
    assert len(seen) == len(set(seen))


def test_describe_is_human_readable():
    assert describe("ctrl+enter") == "Ctrl+Enter"
    assert describe("alt+shift+c") == "Alt+Shift+C"


# ---------- 持久化 ----------
def test_shortcuts_roundtrip(tmp_path):
    """改单个键 → 保存 → 重载，值必须原样回来（这是「重启后仍生效」的前提）。"""
    from dataclasses import replace

    from context_pilot.config import Config

    save(Config(), tmp_path)
    config = load(tmp_path)
    assert config.shortcuts.bindings() == scheme_bindings("balanced")

    customized = config.shortcuts.with_binding("view_diff", "ctrl+shift+d")
    save(replace(config, shortcuts=customized), tmp_path)

    reloaded = load(tmp_path)
    # 只动的那一行变了，其余保持方案默认值
    assert reloaded.shortcuts.bindings()["view_diff"] == "ctrl+shift+d"
    assert reloaded.shortcuts.bindings()["enhance"] == "ctrl+enter"
    # scheme 仍是当初套用的方案，便于一键重置
    assert reloaded.shortcuts.scheme == "balanced"


def test_shortcuts_section_survives_unknown_action_in_file(tmp_path):
    """toml 里混进未知动作键时，加载不该炸。"""
    from context_pilot.config import Config, save

    save(Config(), tmp_path)
    path = tmp_path / "config.toml"
    text = path.read_text(encoding="utf-8")
    path.write_text(text + 'unknown_action = "ctrl+k"\n', encoding="utf-8")

    config = load(tmp_path)
    assert "unknown_action" not in config.shortcuts.bindings()
    assert config.shortcuts.bindings()["use"] == "ctrl+u"


def test_shortcuts_config_ignores_unknown_action_assignment():
    """给不存在的动作设绑定要报错，而不是悄悄写进配置。"""
    from context_pilot.config import ShortcutsConfig

    with pytest.raises(ValueError):
        ShortcutsConfig().with_binding("不存在的动作", "ctrl+k")
