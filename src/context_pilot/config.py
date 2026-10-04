"""应用配置：读写 ~/.context-pilot/config.toml。

配置与密钥都在用户目录，不进版本库。密钥只从配置读取，不写日志。
写回时整体重渲染模板，保证文件结构与字段注释始终一致。
"""

import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path

_DEFAULT_DIR = Path.home() / ".context-pilot"
_CONFIG_NAME = "config.toml"


@dataclass(frozen=True)
class GeneralConfig:
    project_root: str = ""
    hotkey: str = "ctrl+shift+e"


@dataclass(frozen=True)
class LlmConfig:
    provider: str = "stub"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o-mini"
    timeout: float = 60.0


@dataclass(frozen=True)
class MemoryConfig:
    enabled: bool = True


@dataclass(frozen=True)
class ContextConfig:
    max_tokens: int = 6000
    rules_tokens: int = 1500
    memory_tokens: int = 1000
    code_tokens: int = 3500


@dataclass(frozen=True)
class BehaviorConfig:
    autostart: bool = False
    auto_copy: bool = True  # 点「使用」后自动写回剪贴板
    close_to_tray: bool = True  # 关窗只隐藏，不退出


@dataclass(frozen=True)
class Config:
    general: GeneralConfig = field(default_factory=GeneralConfig)
    llm: LlmConfig = field(default_factory=LlmConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    behavior: BehaviorConfig = field(default_factory=BehaviorConfig)


def config_path(base_dir: Path | None = None) -> Path:
    return (base_dir or _DEFAULT_DIR) / _CONFIG_NAME


def load(base_dir: Path | None = None) -> Config:
    """读取配置；文件不存在时写入默认模板并返回默认值。"""
    path = config_path(base_dir)
    if not path.exists():
        save(Config(), base_dir)
        return Config()

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    general = data.get("general", {})
    llm = data.get("llm", {})
    memory = data.get("memory", {})
    context = data.get("context", {})
    behavior = data.get("behavior", {})

    return Config(
        general=GeneralConfig(
            project_root=general.get("project_root", ""),
            hotkey=general.get("hotkey", "ctrl+shift+e"),
        ),
        llm=LlmConfig(
            provider=llm.get("provider", "stub"),
            base_url=llm.get("base_url", "https://api.openai.com/v1"),
            api_key=llm.get("api_key", ""),
            model=llm.get("model", "gpt-4o-mini"),
            timeout=float(llm.get("timeout", 60.0)),
        ),
        memory=MemoryConfig(enabled=bool(memory.get("enabled", True))),
        context=ContextConfig(
            max_tokens=int(context.get("max_tokens", 6000)),
            rules_tokens=int(context.get("rules_tokens", 1500)),
            memory_tokens=int(context.get("memory_tokens", 1000)),
            code_tokens=int(context.get("code_tokens", 3500)),
        ),
        behavior=BehaviorConfig(
            autostart=bool(behavior.get("autostart", False)),
            auto_copy=bool(behavior.get("auto_copy", True)),
            close_to_tray=bool(behavior.get("close_to_tray", True)),
        ),
    )


def save(config: Config, base_dir: Path | None = None) -> None:
    """整体重渲染配置文件。"""
    path = config_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render(config), encoding="utf-8")


def _toml_str(value: str) -> str:
    """TOML 字符串转义，防止路径中的反斜杠与引号破坏结构。"""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _render(config: Config) -> str:
    lines = [
        "# ContextPilot 配置（由设置界面生成）",
        "",
        "[general]",
        "# 被增强的项目根目录；留空则用启动时的工作目录",
        f"project_root = {_toml_str(config.general.project_root)}",
        "# 全局热键，形如 ctrl+shift+e",
        f"hotkey = {_toml_str(config.general.hotkey)}",
        "",
        "[llm]",
        "# provider 可选 stub / openai。stub 不联网，用于离线验证链路",
        f"provider = {_toml_str(config.llm.provider)}",
        "# 任何 OpenAI 兼容端点：OpenAI / DeepSeek / Qwen / Ollama / vLLM 等",
        f"base_url = {_toml_str(config.llm.base_url)}",
        f"api_key = {_toml_str(config.llm.api_key)}",
        f"model = {_toml_str(config.llm.model)}",
        f"timeout = {config.llm.timeout}",
        "",
        "[memory]",
        f"enabled = {str(config.memory.enabled).lower()}",
        "",
        "[context]",
        f"max_tokens = {config.context.max_tokens}",
        f"rules_tokens = {config.context.rules_tokens}",
        f"memory_tokens = {config.context.memory_tokens}",
        f"code_tokens = {config.context.code_tokens}",
        "",
        "[behavior]",
        f"autostart = {str(config.behavior.autostart).lower()}",
        f"auto_copy = {str(config.behavior.auto_copy).lower()}",
        f"close_to_tray = {str(config.behavior.close_to_tray).lower()}",
        "",
    ]
    return "\n".join(lines)


def with_updates(config: Config, **overrides) -> Config:
    """返回替换了顶层 section 的新配置（不可变对象，便于测试与局部更新）。"""
    return replace(config, **overrides)
