"""The providers of the user and their keys."""

import json
from pathlib import Path

import pytest
from fake_vault import PREFIX, FakeVault

from wxclaude.core.config.providers import (
    CLAUDE,
    CLAUDE_ID,
    KEY_NONE,
    KEY_STORED,
    MODEL_MAX,
    NAME_MAX,
    Provider,
    ProviderStore,
    fill_tiers,
    new_provider_id,
)
from wxclaude.core.errors import KeyVaultError, ProviderError

pytestmark = pytest.mark.unit

SECRET = "sk-secret-123"


def deepseek(identifier: str = "deepseek") -> Provider:
    return Provider(
        id=identifier,
        name="DeepSeek",
        base_url="https://api.deepseek.com/anthropic",
        tiers=["deepseek-chat", "deepseek-chat", "deepseek-reasoner", "deepseek-reasoner"],
    )


def local() -> Provider:
    return Provider(
        id="lm-studio",
        name="LM Studio",
        base_url="http://127.0.0.1:1234",
        key_source=KEY_NONE,
        tiers=["qwen"],
        send_effort=False,
    )


def store_at(path: Path, vault: FakeVault | None = None) -> ProviderStore:
    """The store of ``path``; a file that does not exist yet is made empty first, as for a user who
    already used the page (a missing file gives the default providers, tested apart)."""
    if not path.exists():
        path.write_text('{"providers": []}', encoding="utf-8")
    return ProviderStore.load(path, vault or FakeVault())


# -- Claude ---------------------------------------------------------------------------------


def test_claude_is_the_first_and_the_default_provider() -> None:
    store = ProviderStore(FakeVault())
    assert store.providers() == [CLAUDE]
    assert store.get(None) is CLAUDE
    assert store.get("") is CLAUDE
    assert CLAUDE.id == "claude"
    assert CLAUDE.is_builtin
    assert not CLAUDE.needs_key
    assert CLAUDE.problem() is None
    assert "sonnet" in CLAUDE.models


def test_an_unknown_provider_is_read_as_claude() -> None:
    store = ProviderStore(FakeVault())
    store.add(deepseek())
    assert store.get("deepseek").name == "DeepSeek"
    assert store.get("gone") is CLAUDE


def test_claude_cannot_be_changed_or_deleted() -> None:
    store = ProviderStore(FakeVault())
    with pytest.raises(ProviderError):
        store.update(CLAUDE)
    with pytest.raises(ProviderError):
        store.remove(CLAUDE_ID)
    with pytest.raises(ProviderError):
        store.add(Provider(id=CLAUDE_ID, name="Mine", base_url="http://x", tiers=["m"]))
    assert store.providers() == [CLAUDE]


# -- adding, changing, removing -------------------------------------------------------------


def test_providers_keep_the_order_they_were_added_in() -> None:
    store = ProviderStore(FakeVault())
    store.add(deepseek())
    store.add(local())
    assert [p.id for p in store.providers()] == ["claude", "deepseek", "lm-studio"]


def test_the_store_keeps_its_own_copy_of_a_provider() -> None:
    store = ProviderStore(FakeVault())
    provider = deepseek()
    store.add(provider)
    provider.name = "Changed outside"
    assert store.get("deepseek").name == "DeepSeek"


def test_a_provider_that_exists_cannot_be_added_again() -> None:
    store = ProviderStore(FakeVault())
    store.add(deepseek())
    with pytest.raises(ProviderError):
        store.add(deepseek())


@pytest.mark.parametrize(
    ("change", "text"),
    [
        ({"name": "  "}, "name"),
        ({"base_url": "api.deepseek.com"}, "http"),
        ({"base_url": "ftp://x"}, "http"),
        ({"base_url": "http://a b"}, "http"),
        ({"base_url": ""}, "http"),
    ],
)
def test_a_provider_that_is_not_valid_is_refused(change: dict[str, object], text: str) -> None:
    provider = deepseek()
    for key, value in change.items():
        setattr(provider, key, value)
    assert provider.problem() is not None
    assert text in (provider.problem() or "")
    with pytest.raises(ProviderError):
        ProviderStore(FakeVault()).add(provider)


def test_the_name_and_the_models_have_a_longest_length() -> None:
    provider = deepseek()
    provider.name = "x" * NAME_MAX
    assert provider.problem() is None
    provider.name = "x" * (NAME_MAX + 1)
    assert str(NAME_MAX) in (provider.problem() or "")
    provider = deepseek()
    provider.tiers = ["m" * MODEL_MAX, "b", "c", "d"]
    assert provider.problem() is None
    provider.tiers = ["m" * (MODEL_MAX + 1), "b", "c", "d"]
    assert str(MODEL_MAX) in (provider.problem() or "")
    with pytest.raises(ProviderError):
        ProviderStore(FakeVault()).add(provider)


def test_a_provider_without_a_model_is_refused() -> None:
    provider = deepseek()
    provider.tiers = []
    assert "model" in (provider.problem() or "")
    with pytest.raises(ProviderError):
        ProviderStore(FakeVault()).add(provider)


@pytest.mark.parametrize(
    ("entries", "expected"),
    [
        (["a", "b", "c", "d"], ["a", "b", "c", "d"]),
        (["", "b", "", ""], ["b", "b", "b", "b"]),  # the weakest given fills the empty ones
        (["", "", "c", "d"], ["c", "c", "c", "d"]),
        (["a"], ["a", "a", "a", "a"]),
        ([" a ", "  ", "c", ""], ["a", "a", "c", "a"]),
        (["a", "b", "c", "d", "e"], ["a", "b", "c", "d"]),
        (["", " ", "", ""], []),
        ([], []),
    ],
)
def test_the_empty_ranks_take_the_weakest_model_given(
    entries: list[str], expected: list[str]
) -> None:
    assert fill_tiers(entries) == expected
    assert Provider(id="x", name="X", tiers=entries).tiers == expected


def test_the_models_and_the_aliases_come_from_the_ranks() -> None:
    provider = Provider(id="x", name="X", tiers=["small", "", "big", "huge"])
    assert provider.tiers == ["small", "small", "big", "huge"]
    assert provider.models == ["small", "big", "huge"]  # each once, smallest first
    assert provider.aliases == {"haiku": "small", "sonnet": "small", "opus": "big"}
    assert CLAUDE.models == ["haiku", "sonnet", "opus", "fable"]


def test_a_provider_is_updated_by_its_id() -> None:
    store = ProviderStore(FakeVault())
    store.add(deepseek())
    changed = deepseek()
    changed.name = "DeepSeek V4"
    changed.send_effort = False
    store.update(changed)
    assert store.get("deepseek").name == "DeepSeek V4"
    assert not store.get("deepseek").send_effort
    with pytest.raises(ProviderError):
        store.update(local())


def test_removing_a_provider_removes_its_key() -> None:
    store = ProviderStore(FakeVault())
    store.add(deepseek())
    store.set_key("deepseek", SECRET)
    store.remove("deepseek")
    assert store.providers() == [CLAUDE]
    assert not store.has_key("deepseek")
    with pytest.raises(ProviderError):
        store.remove("deepseek")


@pytest.mark.parametrize(
    ("name", "taken", "expected"),
    [
        ("My server", set(), "my-server"),
        ("DeepSeek", {"deepseek"}, "deepseek-2"),
        ("DeepSeek", {"deepseek", "deepseek-2"}, "deepseek-3"),
        ("Claude", set(), "claude-2"),
        ("  ", set(), "provider"),
        ("Été/ça", set(), "t-a"),
    ],
)
def test_new_provider_id(name: str, taken: set[str], expected: str) -> None:
    assert new_provider_id(name, taken) == expected


# -- the file -------------------------------------------------------------------------------


def test_the_providers_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "providers.json"
    store = store_at(path)
    store.add(deepseek())
    store.add(local())
    store.save()
    loaded = store_at(path)
    assert loaded.warning == ""
    assert loaded.providers() == [CLAUDE, deepseek(), local()]


def test_the_variables_of_a_provider_round_trip_and_an_old_file_has_none(tmp_path: Path) -> None:
    path = tmp_path / "providers.json"
    store = store_at(path)
    provider = deepseek()
    provider.env = {"API_TIMEOUT_MS": "600000"}
    store.add(provider)
    store.save()
    assert store_at(path).get("deepseek").env == {"API_TIMEOUT_MS": "600000"}
    old = deepseek().to_dict()
    del old["env"]
    path.write_text(json.dumps({"providers": [old]}), encoding="utf-8")
    assert store_at(path).get("deepseek").env == {}


def test_a_file_cannot_make_a_provider_set_another_variable(tmp_path: Path) -> None:
    path = tmp_path / "providers.json"
    entry = deepseek().to_dict()
    entry["env"] = {"API_TIMEOUT_MS": "5", "ANTHROPIC_BASE_URL": "http://evil", "PATH": "x"}
    path.write_text(json.dumps({"providers": [entry]}), encoding="utf-8")
    assert store_at(path).get("deepseek").env == {"API_TIMEOUT_MS": "5"}


def test_the_variables_are_stripped_and_an_empty_one_is_not_set() -> None:
    provider = Provider(
        id="p",
        name="P",
        base_url="http://x",
        tiers=["m"],
        env={"API_TIMEOUT_MS": " 600 ", "CLAUDE_CODE_MAX_CONTEXT_TOKENS": "  "},
    )
    assert provider.env == {"API_TIMEOUT_MS": "600"}


@pytest.mark.parametrize("value", ["abc", "0", "-5", "1.5", chr(0xFF16) + chr(0xFF10)])
def test_a_value_that_is_not_a_whole_number_above_zero_is_a_problem(value: str) -> None:
    provider = deepseek()
    provider.env = {"API_TIMEOUT_MS": value}
    assert provider.problem() == "The value of API_TIMEOUT_MS is a whole number above zero."


def test_a_variable_that_is_not_in_the_list_is_a_problem() -> None:
    provider = deepseek()
    provider.env = {"ANTHROPIC_BASE_URL": "http://evil"}
    assert provider.problem() == "The variable ANTHROPIC_BASE_URL cannot be set by a provider."


def test_without_a_path_nothing_is_written(tmp_path: Path) -> None:
    store = ProviderStore(FakeVault())
    store.add(deepseek())
    store.save()
    assert list(tmp_path.iterdir()) == []


def test_a_missing_file_gives_the_default_providers(tmp_path: Path) -> None:
    store = ProviderStore.load(tmp_path / "providers.json", FakeVault())
    assert [p.id for p in store.providers()] == ["claude", "deepseek", "ollama"]
    assert store.warning == ""
    deep, ollama = store.get("deepseek"), store.get("ollama")
    assert deep.needs_key
    assert not store.has_key("deepseek")
    assert deep.credit_method == "deepseek"
    assert not ollama.needs_key
    assert ollama.base_url == "http://localhost:11434"
    assert all(provider.problem() is None for provider in (deep, ollama))


def test_the_default_providers_are_not_written_until_the_user_changes_something(
    tmp_path: Path,
) -> None:
    ProviderStore.load(tmp_path / "providers.json", FakeVault())
    assert list(tmp_path.iterdir()) == []


def test_a_file_that_exists_is_all_there_is_so_a_deleted_default_stays_deleted(
    tmp_path: Path,
) -> None:
    path = tmp_path / "providers.json"
    first = ProviderStore.load(path, FakeVault())
    first.remove("deepseek")
    first.save()
    assert [p.id for p in ProviderStore.load(path, FakeVault()).providers()] == [
        "claude",
        "ollama",
    ]
    path.write_text('{"providers": []}', encoding="utf-8")
    assert ProviderStore.load(path, FakeVault()).providers() == [CLAUDE]


def test_the_default_providers_of_two_stores_do_not_share_their_state(tmp_path: Path) -> None:
    one = ProviderStore.load(tmp_path / "one.json", FakeVault())
    one.get("ollama").tiers[0] = "changed"
    other = ProviderStore.load(tmp_path / "two.json", FakeVault())
    assert other.get("ollama").tiers[0] == "qwen3:4b"


def test_a_damaged_file_is_set_aside_and_the_user_is_told(tmp_path: Path) -> None:
    path = tmp_path / "providers.json"
    path.write_text("{not json", encoding="utf-8")
    store = store_at(path)
    assert store.providers() == [CLAUDE]
    assert "providers.json" in store.warning
    assert (tmp_path / "providers.json.corrupt").exists()


def test_a_damaged_file_gives_its_backup(tmp_path: Path) -> None:
    path = tmp_path / "providers.json"
    first = store_at(path)
    first.add(deepseek())
    first.save()
    first.add(local())
    first.save()  # the first version is now the backup
    path.write_text("{not json", encoding="utf-8")
    store = store_at(path)
    assert [p.id for p in store.providers()] == ["claude", "deepseek"]
    assert "backup" in store.warning


def test_entries_that_are_not_well_formed_are_left_out(tmp_path: Path) -> None:
    path = tmp_path / "providers.json"
    good = deepseek().to_dict()
    entries = [
        "text",
        {"name": "No id"},
        {"id": "no-name"},
        {"id": "claude", "name": "Impostor"},
        good,
        dict(good, name="Same id twice"),
    ]
    path.write_text(json.dumps({"providers": entries}), encoding="utf-8")
    store = store_at(path)
    assert [p.id for p in store.providers()] == ["claude", "deepseek"]
    assert store.get("deepseek").name == "DeepSeek"


def test_the_fields_of_an_entry_that_are_not_valid_take_their_default(tmp_path: Path) -> None:
    path = tmp_path / "providers.json"
    entry = {
        "id": "x",
        "name": "X",
        "base_url": 3,
        "key_source": "the credential manager",
        "tiers": ["a", " b ", 4, ""],
        "send_effort": "no",
    }
    path.write_text(json.dumps({"providers": [entry]}), encoding="utf-8")
    provider = store_at(path).get("x")
    assert provider.base_url == ""
    assert provider.key_source == KEY_STORED
    assert provider.tiers == ["a", "b", "a", "a"]
    assert provider.send_effort is True


def test_the_methods_are_kept_and_an_old_file_takes_the_defaults(tmp_path: Path) -> None:
    path = tmp_path / "providers.json"
    store = store_at(path)
    store.add(
        Provider(
            id="x",
            name="X",
            base_url="http://x",
            tiers=["a"],
            models_method="none",
            credit_method="deepseek",
        )
    )
    store.save()
    kept = store_at(path).get("x")
    assert (kept.models_method, kept.credit_method) == ("none", "deepseek")
    entry = {"id": "y", "name": "Y", "tiers": ["a"]}  # written before the methods
    path.write_text(json.dumps({"providers": [entry, {**entry, "id": "z", "models_method": 3}]}))
    old = store_at(path)
    for identifier in ("y", "z"):
        provider = old.get(identifier)
        assert (provider.models_method, provider.credit_method) == ("v1", "none")


def test_a_file_written_before_the_ranks_gives_its_first_models(tmp_path: Path) -> None:
    path = tmp_path / "providers.json"
    entry = {"id": "x", "name": "X", "models": ["a", "b"], "aliases": {"haiku": "a"}}
    path.write_text(json.dumps({"providers": [entry]}), encoding="utf-8")
    assert store_at(path).get("x").tiers == ["a", "b", "a", "a"]


# -- the key --------------------------------------------------------------------------------


def test_a_key_is_saved_encrypted_and_read_back(tmp_path: Path) -> None:
    path = tmp_path / "providers.json"
    store = store_at(path)
    store.add(deepseek())
    assert not store.has_key("deepseek")
    store.set_key("deepseek", f"  {SECRET}\n")
    assert store.has_key("deepseek")
    assert store.key("deepseek") == SECRET
    store.save()
    text = path.read_text(encoding="utf-8")
    assert SECRET not in text
    assert SECRET[::-1] in text  # what the fake vault made of it
    reloaded = store_at(path)
    assert reloaded.has_key("deepseek")
    assert reloaded.key("deepseek") == SECRET


def test_the_key_is_not_in_the_provider(tmp_path: Path) -> None:
    store = ProviderStore(FakeVault())
    store.add(deepseek())
    store.set_key("deepseek", SECRET)
    assert "key" not in store.get("deepseek").to_dict()


def test_a_key_can_be_replaced_and_removed(tmp_path: Path) -> None:
    store = ProviderStore(FakeVault())
    store.add(deepseek())
    store.set_key("deepseek", "one")
    store.set_key("deepseek", "two")
    assert store.key("deepseek") == "two"
    store.remove_key("deepseek")
    store.remove_key("deepseek")  # nothing happens
    assert not store.has_key("deepseek")
    with pytest.raises(ProviderError, match="DeepSeek"):
        store.key("deepseek")


def test_a_key_needs_a_provider_and_a_value() -> None:
    store = ProviderStore(FakeVault())
    store.add(deepseek())
    with pytest.raises(ProviderError):
        store.set_key("gone", SECRET)
    with pytest.raises(ProviderError):
        store.set_key("deepseek", "   ")
    with pytest.raises(ProviderError):
        store.set_key("claude", SECRET)


def test_a_key_that_cannot_be_decrypted_gives_a_clear_error(tmp_path: Path) -> None:
    path = tmp_path / "providers.json"
    store = store_at(path)
    store.add(deepseek())
    store.set_key("deepseek", SECRET)
    store.save()
    other_account = store_at(path, FakeVault(locked=True))
    assert other_account.has_key("deepseek")
    with pytest.raises(KeyVaultError, match=r"DeepSeek.*enter it again"):
        other_account.key("deepseek")
    # The blob is kept: the user can still delete or replace it.
    other_account.save()
    assert PREFIX in path.read_text(encoding="utf-8")


def test_the_key_of_a_provider_that_needs_none() -> None:
    assert not local().needs_key
    assert deepseek().needs_key
