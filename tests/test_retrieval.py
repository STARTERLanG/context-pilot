"""检索器单测。"""

import pytest

from context_pilot.project.models import ProjectContext
from context_pilot.retrieval.ignore import SENSITIVE_PATTERNS, is_sensitive
from context_pilot.retrieval.keyword import KeywordRetriever, extract_tokens
from context_pilot.retrieval.base import Retriever
from context_pilot.retrieval.ripgrep import RipgrepRetriever, RipgrepUnavailable
from context_pilot.retrieval.snippet import extract_snippet, find_matching_lines


def _project(tmp_path) -> ProjectContext:
    return ProjectContext(root=tmp_path.resolve())


def test_extract_tokens_filters_short_words():
    assert extract_tokens("修一下 OrderService 接口 api") == ["orderservice", "api"]


def test_search_ranks_filename_match_above_content_match(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "order.py").write_text("def handle(): pass\n", encoding="utf-8")
    (src / "other.py").write_text("order order order\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "order.py").write_text("order\n", encoding="utf-8")

    results = KeywordRetriever().search("order", _project(tmp_path))
    sources = [item.source for item in results]

    # 文件名命中排第一；node_modules 被忽略
    assert sources[0].endswith("order.py")
    assert not any("node_modules" in s for s in sources)


def test_search_ignores_sensitive_files(tmp_path):
    (tmp_path / ".env").write_text("SECRET=order\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("order\n", encoding="utf-8")

    sources = [i.source for i in KeywordRetriever().search("order", _project(tmp_path))]

    assert ".env" not in sources
    assert "app.py" in sources


def test_search_returns_empty_for_pure_chinese_query(tmp_path):
    (tmp_path / "app.py").write_text("order\n", encoding="utf-8")
    assert KeywordRetriever().search("修一下订单接口", _project(tmp_path)) == []


# ── ripgrep 敏感过滤（回归锁定）──────────────────────────────────────
# 背景：RipgrepRetriever 是 pipeline 的默认首选检索器，但它导入了
# SENSITIVE_PATTERNS / TEXT_SUFFIXES 却从未使用，导致装了 rg 的机器上
# 敏感文件会绕过 keyword/vector/ast 都做过的那层过滤，直接进上下文。


@pytest.fixture
def rg(tmp_path):
    try:
        return RipgrepRetriever()
    except RipgrepUnavailable:
        pytest.skip("本机没有 ripgrep")


def test_ripgrep_ignores_sensitive_files(tmp_path, rg):
    (tmp_path / ".env").write_text("SECRET=order_token\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("order = 1\n", encoding="utf-8")

    sources = [i.source for i in rg.search("order", _project(tmp_path))]

    assert "app.py" in sources
    assert not any(".env" in s for s in sources)


def test_ripgrep_ignores_secret_files(tmp_path, rg):
    """凭证类文件：即便新命名的私钥/云凭据也不该进上下文。"""
    (tmp_path / "id_rsa").write_text("-----BEGIN order KEY-----\n", encoding="utf-8")
    (tmp_path / "credentials").write_text("password=order\n", encoding="utf-8")
    (tmp_path / "secrets.yaml").write_text("token: order\n", encoding="utf-8")
    (tmp_path / "ok.py").write_text("order = 1\n", encoding="utf-8")

    sources = [i.source for i in rg.search("order", _project(tmp_path))]

    assert "ok.py" in sources
    for banned in ("id_rsa", "credentials", "secrets.yaml"):
        assert not any(banned in s for s in sources)


def test_ripgrep_ignores_non_text_files(tmp_path, rg):
    """二进制/无关后缀不应被当作代码片段注入。"""
    (tmp_path / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\norder")
    (tmp_path / "ok.py").write_text("order = 1\n", encoding="utf-8")

    sources = [i.source for i in rg.search("order", _project(tmp_path))]

    assert "ok.py" in sources
    assert not any(s.endswith(".png") for s in sources)


# ── 敏感模式覆盖面 ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "filename",
    [
        ".env",
        ".env.production",
        ".npmrc",
        ".netrc",
        "id_rsa",
        "id_ed25519",
        "id_rsa.pub",
        "server.pem",
        "server.key",
        "keystore.jks",
        "client.p12",
        "credentials",      # 无扩展名也要命中（原 "credentials." 漏网）
        "credentials.json",
        "secrets.yaml",
        "service-account.json",
        "token.json",
    ],
)
def test_is_sensitive_covers_common_secret_files(filename):
    from pathlib import Path

    assert is_sensitive(Path(filename)), f"{filename} 应当判定为敏感文件"


def test_is_sensitive_case_insensitive():
    from pathlib import Path

    assert is_sensitive(Path(".ENV"))
    assert is_sensitive(Path("Id_Rsa"))


def test_sensitive_patterns_include_classic_env_tuple_members():
    """.env / .pem / .key 这些 PRD 明文点名的项必须仍在名单里。"""
    for required in (".env", ".pem", ".key"):
        assert required in SENSITIVE_PATTERNS



def test_keyword_retriever_satisfies_protocol():
    assert isinstance(KeywordRetriever(), Retriever)


def test_search_returns_hit_snippet_with_line_numbers(tmp_path):
    """命中时返回精确片段与行号区间，而非整文件。"""
    src = tmp_path / "src"
    src.mkdir()
    (src / "svc.py").write_text(
        "class Svc:\n"
        "    def __init__(self):\n"
        "        pass\n"
        "    def handle_order(self):\n"
        "        return 1\n",
        encoding="utf-8",
    )

    results = KeywordRetriever().search("handle_order", _project(tmp_path))
    assert results, "应命中 svc.py"

    item = next(r for r in results if r.source.endswith("svc.py"))
    assert "handle_order" in item.snippet
    assert item.line_start is not None and item.line_end is not None
    assert item.line_start <= item.line_end
    # 片段应远小于整文件，体现「按需」而非整文件注入
    assert len(item.snippet) < len(item.content)


def test_find_matching_lines_returns_1_based_line_numbers():
    text = "a\nhandle_order\nc\nhandle_order\ne\n"
    assert find_matching_lines(text, ["handle_order"]) == [2, 4]


def test_extract_snippet_includes_context_lines():
    text = "\n".join(f"line{i}" for i in range(1, 11))
    snippet, start, end = extract_snippet(text, [5])
    assert "line5" in snippet
    assert start <= 5 <= end
    # 命中行前后各保留上下文行
    assert "line3" in snippet
    assert "line7" in snippet
