"""模型配置 CRUD 单测。"""

from context_pilot.models.profiles import ProfileStore


def _store(tmp_path):
    return ProfileStore(base_dir=tmp_path)


def test_add_list_and_get(tmp_path):
    store = _store(tmp_path)
    profile = store.add(
        name="deepseek",
        provider="openai",
        base_url="https://api.deepseek.com/v1",
        api_key="sk-secret-123456",
        model="deepseek-chat",
        temperature=0.3,
        max_tokens=8000,
        enabled=False,
    )

    assert profile.id
    assert profile.name == "deepseek"
    assert store.list()[0].id == profile.id
    assert store.get(profile.id) is not None


def test_api_key_masked_in_listing(tmp_path):
    store = _store(tmp_path)
    profile = store.add(
        name="p", provider="openai", base_url="https://x",
        api_key="sk-abcdefghijklmnop", model="m",
        temperature=0.2, max_tokens=100, enabled=False,
    )
    listed = store.list()[0]
    # 脱敏：不含完整 key，含 ****
    assert "sk-abcdefghijklmnop" not in listed.api_key
    assert "****" in listed.api_key


def test_reveal_key_returns_plaintext(tmp_path):
    store = _store(tmp_path)
    profile = store.add(
        name="p", provider="openai", base_url="https://x",
        api_key="sk-topsecret", model="m",
        temperature=0.2, max_tokens=100, enabled=False,
    )
    assert store.reveal_key_by_id(profile.id) == "sk-topsecret"


def test_update_and_delete(tmp_path):
    store = _store(tmp_path)
    profile = store.add(
        name="p", provider="openai", base_url="https://x",
        api_key="k", model="m", temperature=0.2, max_tokens=100, enabled=False,
    )
    updated = store.update(profile.id, name="p2", model="m2", temperature=0.5)
    assert updated is not None
    assert updated.name == "p2"
    assert updated.model == "m2"
    assert updated.temperature == 0.5

    assert store.delete(profile.id) is True
    assert store.get(profile.id) is None


def test_set_enabled_allows_multiple_effective(tmp_path):
    """生效是多选：勾选第二条不会取消第一条。"""
    store = _store(tmp_path)
    a = store.add(name="a", provider="openai", base_url="x", api_key="k",
                  model="m", temperature=0.2, max_tokens=1, enabled=False)
    b = store.add(name="b", provider="openai", base_url="x", api_key="k",
                  model="m", temperature=0.2, max_tokens=1, enabled=False)

    store.set_enabled(a.id, True)
    store.set_enabled(b.id, True)

    enabled = store.list_enabled()
    assert [p.id for p in enabled] == [a.id, b.id]

    # 单独取消一条，另一条不受影响
    store.set_enabled(a.id, False)
    assert [p.id for p in store.list_enabled()] == [b.id]


def test_update_required_fields_empty_name_rejected(tmp_path):
    """必填校验：name/base_url/model 为空时 add 应报错。"""
    store = _store(tmp_path)
    import pytest

    with pytest.raises(ValueError, match="name"):
        store.add(name="", provider="openai", base_url="x", api_key="k",
                  model="m", temperature=0.2, max_tokens=1, enabled=False)
    with pytest.raises(ValueError, match="base_url"):
        store.add(name="p", provider="openai", base_url="", api_key="k",
                  model="m", temperature=0.2, max_tokens=1, enabled=False)
