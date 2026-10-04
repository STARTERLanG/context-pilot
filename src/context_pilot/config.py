"""应用配置：读取 ~/.context-pilot/config.toml。

配置与密钥都在用户目录，不进版本库。密钥只从配置读取，不写日志。
"""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

_DEFAULT_DIR = Path.home() / ".context-pilot"
_CONFIG_NAME = "config.toml"

# 首次运行时写入的默认配置文件
_TEMPLATE = """\
# ContextPilot 配置

[general]
# 被增强的项目根目录；留空则用启动时的工作目录
project_root = ""

[llm]
# provider 可选 stub / openai。stub 不联网，用于离线验证链路
provider = "stub"
# 任何 OpenAI 兼容端点：OpenAI / DeepSeek / Qwen / Ollama / vLLM 等
base_url = "https://api.openai.com/v1"
api_key = ""
model = "gpt-4o-mini"
timeout = 60.0

[memory]
enabled = true

[context]
max_tokens = 6000
"""


@dataclass(frozen=True)
class LlmConfig:
    provider: str = "stub"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o-mini"
    timeout: float = 60.0


@dataclass(frozen=True)
class GeneralConfig:
    project_root: str = ""


@dataclass(frozen=True)
class MemoryConfig:
    enabled: bool = True


@dataclass(frozen=True)
class ContextConfig:
    max_tokens: int = 6000


@dataclass(frozen=True)
class Config:
    general: GeneralConfig = field(default_factory=GeneralConfig)
    llm: LlmConfig = field(default_factory=LlmConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    context: ContextConfig = field(default_factory=ContextConfig)


def config_path(base_dir: Path | None = None) -> Path:
    return (base_dir or _DEFAULT_DIR) / _CONFIG_NAME


def load(base_dir: Path | None = None) -> Config:
    """读取配置；文件不存在时写入默认模板并返回默认值。"""
    path = config_path(base_dir)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_TEMPLATE, encoding="utf-8")
        return Config()

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    general = data.get("general", {})
    llm = data.get("llm", {})
    memory = data.get("memory", {})
    context = data.get("context", {})

    return Config(
        general=GeneralConfig(project_root=general.get("project_root", "")),
        llm=LlmConfig(
            provider=llm.get("provider", "stub"),
            base_url=llm.get("base_url", "https://api.openai.com/v1"),
            api_key=llm.get("api_key", ""),
            model=llm.get("model", "gpt-4o-mini"),
            timeout=float(llm.get("timeout", 60.0)),
        ),
        memory=MemoryConfig(enabled=bool(memory.get("enabled", True))),
        context=ContextConfig(max_tokens=int(context.get("max_tokens", 6000))),
    )
