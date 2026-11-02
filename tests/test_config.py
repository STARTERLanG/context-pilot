"""配置读写单测。全部隔离到 tmp_path，不触碰用户家目录。"""

from pathlib import Path

from context_pilot.config import (
    BehaviorConfig,
    Config,
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
