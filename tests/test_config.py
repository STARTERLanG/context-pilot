"""配置读写单测。全部隔离到 tmp_path，不触碰用户家目录。"""

from pathlib import Path

import pytest

import context_pilot.config as config_module
from context_pilot.config import (
    BehaviorConfig,
    Config,
    EnhanceHotkeyConfig,
    GeneralConfig,
    LlmConfig,
    config_path,
    load,
    save,
    with_updates,
)


def test_load_creates_default_file_on_first_run(tmp_path):
    config = load(base_dir=tmp_path)

    assert config_path(tmp_path).exists()
    assert config.llm.timeout == 60.0
    assert config.general.hotkey == "ctrl+shift+e"
    assert config.general.agent == "claude"
    assert config.memory.enabled is True


def test_save_then_load_roundtrip(tmp_path):
    original = Config(
        general=GeneralConfig(project_root="D:/work/app", hotkey="ctrl+alt+p"),
        llm=LlmConfig(timeout=30.0),
        behavior=BehaviorConfig(autostart=True, auto_copy=False),
    )

    save(original, base_dir=tmp_path)
    reloaded = load(base_dir=tmp_path)

    assert reloaded.general.project_root == "D:/work/app"
    assert reloaded.general.hotkey == "ctrl+alt+p"
    assert reloaded.llm.timeout == 30.0
    assert reloaded.behavior.autostart is True
    assert reloaded.behavior.auto_copy is False


def test_save_escapes_windows_path(tmp_path):
    """Windows 反斜杠路径写回后仍能解析，不会破坏 TOML 结构。"""
    config = with_updates(
        Config(), general=GeneralConfig(project_root=r"D:\work\app", hotkey="ctrl+shift+e")
    )

    save(config, base_dir=tmp_path)
    reloaded = load(base_dir=tmp_path)

    assert reloaded.general.project_root == r"D:\work\app"


def test_with_updates_replaces_only_target_section():
    original = Config()
    updated = with_updates(original, llm=LlmConfig(timeout=15.0))

    assert updated.llm.timeout == 15.0
    assert updated.general.hotkey == original.general.hotkey  # 其他 section 不变


def test_load_partial_file_falls_back_to_defaults(tmp_path):
    Path(tmp_path, "config.toml").write_text("[llm]\ntimeout = 12.0\n", encoding="utf-8")

    config = load(base_dir=tmp_path)

    assert config.llm.timeout == 12.0
    assert config.context.max_tokens == 6000


def test_legacy_llm_fields_are_ignored(tmp_path):
    """旧版 config.toml 里的 base_url/api_key/model 不再被读取。

    它们已由「模型配置」库取代；继续读取会让两套来源互相矛盾。
    """
    Path(tmp_path, "config.toml").write_text(
        '[llm]\nprovider = "openai"\nbase_url = "https://old/v1"\n'
        'api_key = "sk-old"\nmodel = "old-model"\n',
        encoding="utf-8",
    )

    config = load(base_dir=tmp_path)

    assert not hasattr(config.llm, "api_key")
    assert not hasattr(config.llm, "base_url")
    assert not hasattr(config.llm, "model")
    assert not hasattr(config.llm, "provider")


def test_save_drops_legacy_llm_fields(tmp_path):
    """写回时旧字段消失，配置文件与内存模型保持一致。"""
    Path(tmp_path, "config.toml").write_text(
        '[llm]\napi_key = "sk-old"\nmodel = "old"\n', encoding="utf-8"
    )

    save(load(base_dir=tmp_path), base_dir=tmp_path)
    text = Path(tmp_path, "config.toml").read_text(encoding="utf-8")

    assert "api_key" not in text
    assert "base_url" not in text
    assert "timeout" in text


def test_enhance_hotkey_defaults(tmp_path):
    """增强热键默认值：默认模式=default、默认模型=空、自动粘贴=关、默认项目=空。"""
    config = load(base_dir=tmp_path)

    assert config.enhance_hotkey.default_style == "default"
    assert config.enhance_hotkey.default_model_id == ""
    assert config.enhance_hotkey.auto_paste is False
    assert config.enhance_hotkey.default_project_id == ""


def test_enhance_hotkey_roundtrip(tmp_path):
    """增强热键默认值写入配置后可完整读回。"""
    config = with_updates(
        Config(),
        enhance_hotkey=EnhanceHotkeyConfig(
            default_style="professional",
            default_model_id="abc123",
            auto_paste=True,
            default_project_id="proj-1",
        ),
    )

    save(config, base_dir=tmp_path)
    reloaded = load(base_dir=tmp_path)

    assert reloaded.enhance_hotkey.default_style == "professional"
    assert reloaded.enhance_hotkey.default_model_id == "abc123"
    assert reloaded.enhance_hotkey.auto_paste is True
    assert reloaded.enhance_hotkey.default_project_id == "proj-1"


def test_enhance_hotkey_partial_falls_back_to_defaults(tmp_path):
    """旧配置没有 enhance_hotkey section 时，各字段回落默认值。"""
    Path(tmp_path, "config.toml").write_text("[general]\nhotkey = \"ctrl+shift+e\"\n", encoding="utf-8")

    config = load(base_dir=tmp_path)

    assert config.enhance_hotkey.default_style == "default"
    assert config.enhance_hotkey.auto_paste is False
    assert config.enhance_hotkey.default_project_id == ""


def test_malformed_scalar_values_fall_back_individually(tmp_path):
    """单个字段写坏只回落该字段，布尔字符串不得被 bool() 静默反转。"""
    Path(tmp_path, "config.toml").write_text(
        '[llm]\ntimeout = "abc"\n'
        '[memory]\nenabled = "false"\n'
        '[context]\nmax_tokens = "oops"\n'
        '[behavior]\nauto_copy = "false"\n'
        '[enhance_hotkey]\nauto_paste = "yes"\n',
        encoding="utf-8",
    )

    config = load(base_dir=tmp_path)

    assert config.llm.timeout == 60.0
    assert config.memory.enabled is False
    assert config.context.max_tokens == 6000
    assert config.behavior.auto_copy is False
    assert config.enhance_hotkey.auto_paste is True


def test_save_failure_keeps_previous_file_and_no_temp_left(tmp_path, monkeypatch):
    """写盘中断时旧配置必须完好，且不留半截临时文件。"""
    save(Config(), base_dir=tmp_path)
    original = config_path(tmp_path).read_text(encoding="utf-8")

    def _fail_replace(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(config_module.os, "replace", _fail_replace)
    with pytest.raises(OSError):
        save(with_updates(Config(), llm=LlmConfig(timeout=1.0)), base_dir=tmp_path)

    assert config_path(tmp_path).read_text(encoding="utf-8") == original
    assert list(tmp_path.glob(".config.toml.*.tmp")) == []
