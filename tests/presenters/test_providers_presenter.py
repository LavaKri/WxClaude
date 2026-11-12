"""The Providers page of the Preferences, with a fake view: no wx, no window."""

from pathlib import Path

import pytest
from fake_vault import FakeVault

from wxclaude.core.config.providers import KEY_NONE, Provider, ProviderStore
from wxclaude.presenters.provider_form_presenter import ProviderEdit
from wxclaude.presenters.providers_presenter import ProvidersPresenter

pytestmark = pytest.mark.unit


def form(
    name: str = "DeepSeek", url: str = "https://api.deepseek.com/anthropic", *, key: str = ""
) -> ProviderEdit:
    """What the form gives back for a provider (a key typed in it if ``key``)."""
    return ProviderEdit(Provider(id="", name=name, base_url=url, tiers=["deepseek-chat"]), key=key)


class FakeView:
    """Answers the forms with the edits the test queued; records what is shown."""

    def __init__(self) -> None:
        self.forms: list[ProviderEdit | None] = []  # the answers, in order
        self.asked: list[ProviderEdit | None] = []  # what the forms were given
        self.sure = True
        self.lines: list[str] = []
        self.selected = -1
        self.errors: list[str] = []

    def show_providers(self, lines: list[str], selected: int) -> None:
        self.lines, self.selected = lines, selected

    def ask_provider(self, edit: ProviderEdit | None) -> ProviderEdit | None:
        self.asked.append(edit)
        return self.forms.pop(0) if self.forms else None

    def confirm_delete(self, name: str) -> bool:
        return self.sure

    def show_error(self, message: str) -> None:
        self.errors.append(message)


def page(tmp_path: Path) -> tuple[ProvidersPresenter, FakeView, ProviderStore]:
    path = tmp_path / "providers.json"
    path.write_text(
        '{"providers": []}', encoding="utf-8"
    )  # a user who has none (not a first start)
    store = ProviderStore.load(path, FakeVault())
    view = FakeView()
    return ProvidersPresenter(view, store), view, store


def test_the_page_starts_with_claude_selected(tmp_path: Path) -> None:
    presenter, view, _store = page(tmp_path)
    assert view.lines == ["Claude, built in"]
    assert view.selected == 0
    assert not presenter.can_edit()


def test_adding_a_provider_keeps_it_selects_it_and_writes_the_file(tmp_path: Path) -> None:
    presenter, view, store = page(tmp_path)
    view.forms = [form()]
    presenter.add()
    assert view.lines == [
        "Claude, built in",
        "DeepSeek, https://api.deepseek.com/anthropic, no key",
    ]
    assert view.selected == 1
    assert store.get("deepseek").name == "DeepSeek"
    assert (tmp_path / "providers.json").exists()
    assert presenter.can_edit()


def test_two_providers_with_the_same_name_get_their_own_id(tmp_path: Path) -> None:
    presenter, view, store = page(tmp_path)
    view.forms = [form(), form()]
    presenter.add()
    presenter.add()
    assert [p.id for p in store.providers()] == ["claude", "deepseek", "deepseek-2"]


def test_a_form_that_is_not_valid_is_asked_again_with_what_was_typed(tmp_path: Path) -> None:
    presenter, view, store = page(tmp_path)
    wrong = form(url="deepseek.com", key="sk-typed")
    view.forms = [wrong, form()]
    presenter.add()
    assert len(view.errors) == 1
    assert "http" in view.errors[0]
    assert view.asked[1] is wrong  # the second form shows what was typed, key included
    assert [p.id for p in store.providers()] == ["claude", "deepseek"]


def test_a_form_without_any_model_is_asked_again(tmp_path: Path) -> None:
    presenter, view, store = page(tmp_path)
    view.forms = [ProviderEdit(Provider(id="", name="X", base_url="http://x")), form()]
    presenter.add()
    assert len(view.errors) == 1
    assert "model" in view.errors[0]
    assert [p.id for p in store.providers()] == ["claude", "deepseek"]


def test_the_ranks_not_given_take_the_weakest_model_given(tmp_path: Path) -> None:
    presenter, view, store = page(tmp_path)
    given = Provider(id="", name="X", base_url="http://x", tiers=["", "m", "", "big"])
    view.forms = [ProviderEdit(given)]
    presenter.add()
    assert store.get("x").tiers == ["m", "m", "m", "big"]


def test_cancelling_the_form_adds_nothing(tmp_path: Path) -> None:
    presenter, view, store = page(tmp_path)
    presenter.add()
    view.forms = [form(url="bad"), None]
    presenter.add()
    assert store.providers()[1:] == []
    written = (tmp_path / "providers.json").read_text(encoding="utf-8")
    assert written == '{"providers": []}'  # nothing was written over the empty file


def test_a_key_typed_in_the_form_is_saved_encrypted_with_the_provider(tmp_path: Path) -> None:
    presenter, view, store = page(tmp_path)
    view.forms = [form(key="sk-secret")]
    presenter.add()
    assert store.key("deepseek") == "sk-secret"
    assert view.lines[1].endswith("key saved")
    assert "sk-secret" not in " ".join(view.lines)
    assert "sk-secret" not in (tmp_path / "providers.json").read_text(encoding="utf-8")


def test_editing_a_provider_fills_the_form_keeps_its_id_and_its_key(tmp_path: Path) -> None:
    presenter, view, store = page(tmp_path)
    view.forms = [form(key="sk-1")]
    presenter.add()
    view.forms = [ProviderEdit(form(name="DeepSeek V4").provider, had_key=True)]
    presenter.edit()
    asked = view.asked[-1]
    assert asked is not None
    assert asked.provider.name == "DeepSeek"  # the form is filled with the provider
    assert asked.had_key  # and knows that a key is saved
    assert store.get("deepseek").name == "DeepSeek V4"
    assert store.key("deepseek") == "sk-1"
    assert view.lines[1].startswith("DeepSeek V4,")


def test_the_form_gets_a_copy_so_that_cancelling_changes_nothing(tmp_path: Path) -> None:
    presenter, view, store = page(tmp_path)
    view.forms = [form()]
    presenter.add()
    view.forms = []  # cancelled after the form changed its copy
    presenter.edit()
    asked = view.asked[-1]
    assert asked is not None
    asked.provider.name = "Changed"
    assert store.get("deepseek").name == "DeepSeek"


def test_a_key_can_be_replaced_or_removed_from_the_form(tmp_path: Path) -> None:
    presenter, view, store = page(tmp_path)
    view.forms = [form(key="sk-1")]
    presenter.add()
    view.forms = [ProviderEdit(form().provider, had_key=True, key="sk-2")]
    presenter.edit()
    assert store.key("deepseek") == "sk-2"
    view.forms = [ProviderEdit(form().provider, had_key=True, remove_key=True)]
    presenter.edit()
    assert not store.has_key("deepseek")
    assert view.lines[1].endswith("no key")


def test_claude_cannot_be_edited_or_deleted(tmp_path: Path) -> None:
    presenter, view, store = page(tmp_path)
    view.forms = [form()]
    presenter.edit()
    presenter.delete()
    assert view.asked == []
    assert store.providers()[0].is_builtin
    assert view.errors == []


def test_a_provider_that_needs_no_key_takes_none(tmp_path: Path) -> None:
    presenter, view, store = page(tmp_path)
    local = form(name="LM Studio", url="http://127.0.0.1:1234", key="x")
    local.provider.key_source = KEY_NONE
    view.forms = [local]
    presenter.add()
    assert view.lines[1].endswith("no key needed")
    assert not store.has_key("lm-studio")


def test_deleting_asks_first_and_takes_the_key_with_it(tmp_path: Path) -> None:
    presenter, view, store = page(tmp_path)
    view.forms = [form(key="sk-1")]
    presenter.add()
    view.sure = False
    presenter.delete()
    assert store.has_key("deepseek")
    view.sure = True
    presenter.delete()
    assert [p.id for p in store.providers()] == ["claude"]
    assert not store.has_key("deepseek")
    assert view.selected == 0


def test_a_file_that_cannot_be_written_is_reported(tmp_path: Path) -> None:
    presenter, view, _store = page(tmp_path)
    (tmp_path / "providers.json.tmp").mkdir()  # the temporary file cannot be written
    view.forms = [form()]
    presenter.add()
    assert len(view.errors) == 1
    assert view.errors[0].startswith("Cannot write")
