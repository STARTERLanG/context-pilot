"""OpenAI 兼容提供方单测。用 httpx MockTransport，不发起真实网络请求。"""

import asyncio

import httpx
import pytest

from context_pilot.optimizer.openai_provider import (
    OpenAiProvider,
    ProviderError,
    _extract_content,
)
from context_pilot.optimizer.provider import StubProvider
from context_pilot.optimizer.templates import (
    STANDALONE_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    PROFESSIONAL_SYSTEM_PROMPT,
    PLANNING_SYSTEM_PROMPT,
    build_user_message,
    resolve_mode,
    mode_system_prompt,
)


def _response(content: str, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status,
        json={"choices": [{"message": {"content": content}}]},
    )


def test_enhance_returns_content(monkeypatch):
    provider = OpenAiProvider("https://x/v1", "sk-test", "m")

    async def fake_post(self, url, json=None, headers=None):
        assert url.endswith("/chat/completions")
        assert headers["Authorization"] == "Bearer sk-test"
        assert json["messages"][0]["content"] == SYSTEM_PROMPT
        # max_tokens 默认 6000 进入 payload
        assert json["max_tokens"] == 6000
        return _response("## 目标\n\n做点什么")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    result = asyncio.run(provider.enhance("做点什么", context="<rule>a</rule>"))
    assert result == "## 目标\n\n做点什么"


def test_enhance_standalone_uses_standalone_prompt(monkeypatch):
    """无项目（standalone=True）：用「通用提示词润色」的 system，不用任务书 system。"""
    provider = OpenAiProvider("https://x/v1", "sk-test", "m")
    captured: dict = {}

    async def fake_post(self, url, json=None, headers=None):
        captured["payload"] = json
        return _response("优化后的一句话")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    result = asyncio.run(provider.enhance("帮我写个脚本", standalone=True))

    payload = captured["payload"]
    system = payload["messages"][0]["content"]
    user = payload["messages"][1]["content"]
    assert system == STANDALONE_SYSTEM_PROMPT
    assert "优化提示词文本本身" in user  # 任务隔离声明
    assert "<task>" not in user  # 不再有任务书声明
    assert result == "优化后的一句话"


def test_enhance_standalone_omits_task_block(monkeypatch):
    """standalone 用户消息不含 <task> 任务书结构，只保留边界声明 + 原文。"""
    provider = OpenAiProvider("https://x/v1", "sk-test", "m")
    captured: dict = {}

    async def fake_post(self, url, json=None, headers=None):
        captured["payload"] = json
        return _response("ok")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    asyncio.run(provider.enhance("写个函数", standalone=True))

    user = captured["payload"]["messages"][1]["content"]
    assert "写个函数" in user
    assert "<task>" not in user
    assert "<output_style>" not in user


def test_enhance_direct_connection_uses_temperature_1(monkeypatch):
    """直连（无 profile_store）默认 temperature=1.0，对齐服务端默认而非 0.2。"""
    provider = OpenAiProvider("https://x/v1", "sk-test", "m")
    captured: dict = {}

    async def fake_post(self, url, json=None, headers=None):
        captured["payload"] = json
        return _response("ok")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    asyncio.run(provider.enhance("x"))

    assert captured["payload"]["temperature"] == 1.0


def test_enhance_passes_max_tokens_and_style(monkeypatch):
    """长度上限透传到 payload；basic 模式选基础优化 system prompt。"""
    provider = OpenAiProvider("https://x/v1", "sk-test", "m")
    captured: dict = {}

    async def fake_post(self, url, json=None, headers=None):
        captured["payload"] = json
        return _response("ok")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    asyncio.run(provider.enhance("写一句", max_tokens=500, style="basic"))

    payload = captured["payload"]
    assert payload["max_tokens"] == 500
    system = payload["messages"][0]["content"]
    assert "基础优化" in system or "消除" in system  # 基础优化 system prompt


def test_enhance_without_api_key_raises():
    provider = OpenAiProvider("https://x/v1", "", "m")
    with pytest.raises(ProviderError, match="未配置"):
        asyncio.run(provider.enhance("x"))


def test_enhance_401_mentions_auth(monkeypatch):
    provider = OpenAiProvider("https://x/v1", "sk-bad", "m")

    async def fake_post(self, url, json=None, headers=None):
        return httpx.Response(401, json={"error": "bad key"})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    with pytest.raises(ProviderError, match="鉴权"):
        asyncio.run(provider.enhance("x"))


def test_enhance_timeout_raises_provider_error(monkeypatch):
    provider = OpenAiProvider("https://x/v1", "sk-test", "m")

    async def fake_post(self, url, json=None, headers=None):
        raise httpx.TimeoutException("too slow")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    with pytest.raises(ProviderError, match="超时"):
        asyncio.run(provider.enhance("x"))


def test_extract_content_missing_choices_raises():
    with pytest.raises(ProviderError, match="结构异常"):
        _extract_content(httpx.Response(200, json={"choices": []}))


def test_extract_content_empty_raises():
    with pytest.raises(ProviderError, match="空结果"):
        _extract_content(_response("   "))


# ── 结构健壮性：覆盖真实端点返回结构变化时最易漏掉的异常分支 ──────────
# 历史教训：_response() 只造「理想结构」，掩盖了 choices[0].message 缺 content、
# message 非 dict、choices 为 null 等真实世界的结构漂移。以下逐层打桩。


def test_extract_content_choices_null_raises():
    """choices 为 null：既非空列表也非列表，之前会走 TypeError 分支但报错含糊。"""
    with pytest.raises(ProviderError, match="结构异常"):
        _extract_content(httpx.Response(200, json={"choices": None}))


def test_extract_content_choice_not_dict_raises():
    """choices[0] 不是 dict（如字符串/None），取 message 应报结构异常而非崩溃。"""
    with pytest.raises(ProviderError, match="结构异常"):
        _extract_content(httpx.Response(200, json={"choices": ["oops"]}))


def test_extract_content_message_missing_raises():
    """choices[0] 存在但缺 message 字段——最典型的「字段名不同/结构漂移」。"""
    with pytest.raises(ProviderError, match="结构异常"):
        _extract_content(httpx.Response(200, json={"choices": [{"text": "hi"}]}))


def test_extract_content_message_not_dict_raises():
    """message 存在但不是 dict（如 null），取 content 应报结构异常。"""
    with pytest.raises(ProviderError, match="结构异常"):
        _extract_content(httpx.Response(200, json={"choices": [{"message": None}]}))


def test_extract_content_content_none_raises_empty():
    """content 字段存在但为 None：应落入「空结果」而非结构异常（有字段但无内容）。"""
    with pytest.raises(ProviderError, match="空结果"):
        _extract_content(httpx.Response(200, json={"choices": [{"message": {"content": None}}]}))


def test_extract_content_top_level_not_dict_raises():
    """顶层 JSON 不是对象（如列表/标量），data.get 之前必须兜底。"""
    with pytest.raises(ProviderError, match="结构异常"):
        _extract_content(httpx.Response(200, json=[1, 2, 3]))


def test_extract_content_non_object_json_raises():
    """合法 JSON 但非预期结构（如纯字符串），不应抛 JSON 解析错误而应报结构异常。"""
    with pytest.raises(ProviderError, match="结构异常"):
        _extract_content(httpx.Response(200, json="hello"))


def test_build_user_message_wraps_request_and_context():
    message = build_user_message("修一下", "<rule>x</rule>")
    assert "<user_request>" in message
    assert "修一下" in message
    assert "<rule>" in message


def test_build_user_message_without_context_only_wraps_request():
    message = build_user_message("修一下", "")
    assert "<user_request>" in message
    assert "修一下" in message
    assert "<project_context>" not in message


def test_system_prompt_is_action_oriented():
    """提示词取向：意图优先 + 行动指南，避免机械照搬固定区块。"""
    assert "意图" in SYSTEM_PROMPT
    assert "可执行" in SYSTEM_PROMPT
    # 不再强制输出固定的一组空标题
    assert "## Project Context" not in SYSTEM_PROMPT


def test_stub_provider_omits_project_rule_without_context():
    """无项目上下文时，不硬塞「遵循项目约定」这类空泛约束。"""
    result = asyncio.run(StubProvider().enhance("做点什么", context=""))
    assert "## 目标" in result
    assert "做点什么" in result
    assert "遵循项目已有约定" not in result


def test_stub_provider_includes_project_rule_with_context():
    """有项目上下文时，才加入「复用现有抽象」的行动指引。"""
    result = asyncio.run(StubProvider().enhance("做点什么", context="<rule>x</rule>"))
    assert "## 目标" in result
    assert "遵循项目已有约定" in result


def test_stub_provider_uses_chinese_headings():
    """输出骨架标题统一为中文（目标 / 实现步骤 / 验收标准）。"""
    result = asyncio.run(StubProvider().enhance("做点什么", context=""))
    assert "## 目标" in result
    assert "## 实现步骤" in result
    assert "## 验收标准" in result
    # 不再出现英文标题
    assert "## Objective" not in result
    assert "## Steps" not in result


def test_stub_provider_basic_style_skips_structure():
    """基础优化模式：直接返回原文（优化后提示词文本），不输出任务书骨架。"""
    result = asyncio.run(StubProvider().enhance("这句话有点啰嗦", style="basic"))
    assert "这句话有点啰嗦" in result
    assert "## 目标" not in result
    assert "## 实现步骤" not in result
    assert "## 验收标准" not in result


def test_style_instruction_returns_constraint():
    """style_instruction 按预设返回约束段；默认/未知风格无约束（安全兜底）。"""
    from context_pilot.optimizer.templates import style_instruction

    assert style_instruction("default") == ""
    assert style_instruction("unknown") == ""  # 未知风格不注入，安全兜底
    # 带 instruction 的自定义预设仍能注入约束
    from context_pilot.core.models import OutputStyle

    custom = [OutputStyle(key="c", label="x", instruction="只润色不分点", max_tokens=300)]
    assert "只润色不分点" in style_instruction("c", custom)


# ── 防「模型直接回答问题」回归（改写任务边界）──────────────────────────


def test_system_prompt_forbids_answering_the_request():
    """系统提示必须显式禁止「直接回答/给方案」，否则模型会把提问当任务执行。"""
    assert "不回答原文的问题" in SYSTEM_PROMPT
    assert "不写实现代码" in SYSTEM_PROMPT
    # 必须点明产物是给下游 Agent 的指令，而不是答案本身
    assert "下游 Agent" in SYSTEM_PROMPT
    # 上下文代码只能当参考资料，不能当续写底稿
    assert "参考素材" in SYSTEM_PROMPT


def test_system_prompt_demands_no_preamble():
    """输出第一行就是正文，禁止「以下是优化后的结果」这类开场白。"""
    assert "不要任何前言" in SYSTEM_PROMPT


def test_user_message_marks_request_as_rewrite_material():
    """用户消息必须声明 <user_request> 是待改写素材，而非待回答的问题。"""
    message = build_user_message("怎么实现登录", "<rule>x</rule>")
    assert "<task>" in message
    assert "改写" in message
    assert "不要回答它" in message


def test_style_instruction_not_mixed_into_user_request():
    """附加约束独立成 <output_style>，不再混进待改写正文。

    这是「提示词混乱」的关键回归点：若指令与素材混在 <user_request> 内，
    模型无法分辨哪些是要改写的内容、哪些是对它的要求。
    """
    from context_pilot.core.models import OutputStyle

    custom = [OutputStyle(key="c", label="x", instruction="只润色不分点", max_tokens=300)]
    message = build_user_message("这句话有点啰嗦", "", style="c", styles=custom)
    assert "<output_style>" in message
    assert "只润色不分点" in message

    request = message.split("<user_request>")[1].split("</user_request>")[0]
    assert "只润色不分点" not in request  # 指令不得出现在待改写正文里
    assert "这句话有点啰嗦" in request  # 正文仍是原始素材


def test_user_message_section_order_and_isolation():
    """结构顺序：task → output_style → context → user_request，互不嵌套。"""
    from context_pilot.core.models import OutputStyle

    custom = [OutputStyle(key="c", label="x", instruction="约束", max_tokens=300)]
    message = build_user_message("修一下", "<rules>r</rules>", style="c", styles=custom)
    assert message.index("<task>") < message.index("<output_style>")
    assert message.index("<output_style>") < message.index("<rules>")
    assert message.index("<rules>") < message.index("<user_request>")


def test_user_message_without_style_has_no_output_style_block():
    """默认风格无约束指令时，不产生空的 <output_style> 段。"""
    assert "<output_style>" not in build_user_message("x", "")


# ── 优化模式（mode）选择 ─────────────────────────────────────────────


def test_resolve_mode_maps_style_to_mode():
    """style（=模式 key）解析为 mode 标识；未知 key 回退 task。"""
    assert resolve_mode("default") == "task"
    assert resolve_mode("basic") == "basic"
    assert resolve_mode("professional") == "professional"
    assert resolve_mode("planning") == "planning"
    assert resolve_mode("unknown") == "task"  # 安全兜底


def test_mode_system_prompt_selects_correct_template():
    """四种模式各选对应 system prompt。"""
    assert mode_system_prompt("task") == SYSTEM_PROMPT
    assert mode_system_prompt("basic") == STANDALONE_SYSTEM_PROMPT
    assert mode_system_prompt("professional") == PROFESSIONAL_SYSTEM_PROMPT
    assert mode_system_prompt("planning") == PLANNING_SYSTEM_PROMPT


def test_enhance_professional_uses_professional_prompt(monkeypatch):
    """专业优化模式：system 用精准化提示词，user 用对应 notice。"""
    provider = OpenAiProvider("https://x/v1", "sk-test", "m")
    captured: dict = {}

    async def fake_post(self, url, json=None, headers=None):
        captured["payload"] = json
        return _response("ok")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    asyncio.run(provider.enhance("写一个泛泛的需求", style="professional"))

    system = captured["payload"]["messages"][0]["content"]
    user = captured["payload"]["messages"][1]["content"]
    assert system == PROFESSIONAL_SYSTEM_PROMPT
    assert "精准" in user or "具体" in user  # 专业优化 notice


def test_enhance_planning_uses_planning_prompt(monkeypatch):
    """步骤化规划模式：system 用步骤化提示词，含角色/目标/步骤结构要求。"""
    provider = OpenAiProvider("https://x/v1", "sk-test", "m")
    captured: dict = {}

    async def fake_post(self, url, json=None, headers=None):
        captured["payload"] = json
        return _response("ok")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    asyncio.run(provider.enhance("做一个复杂需求", style="planning"))

    system = captured["payload"]["messages"][0]["content"]
    assert system == PLANNING_SYSTEM_PROMPT
    assert "角色与目标" in system
    assert "关键步骤" in system
