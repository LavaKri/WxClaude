"""The key button and the check button of the form of a provider, with a fake form."""

from collections.abc import Callable

import pytest
from fake_vault import FakeVault

from wxclaude.core.config.provider_methods import DeepSeekCredit, V1Models
from wxclaude.core.config.providers import KEY_NONE, Provider, ProviderStore
from wxclaude.core.errors import BalanceError, ModelListError
from wxclaude.presenters.provider_form_presenter import ProviderEdit, ProviderFormPresenter

pytestmark = pytest.mark.unit

URL = "https://api.deepseek.com/anthropic"


class FakeForm:
    """Records the buttons and what is shown; runs the task of the check at once."""

    def __init__(self) -> None:
        self.key_button = ("", False)
        self.check_button = False
        self.typed: str | None = None  # what the key dialog answers
        self.asked: list[str] = []
        self.errors: list[str] = []
        self.shown: list[tuple[str, list[str]]] = []
        self.checks = 0

    def set_key_button(self, label: str, enabled: bool) -> None:
        self.key_button = (label, enabled)

    def set_check_button(self, enabled: bool) -> None:
        self.check_button = enabled

    def ask_key(self, name: str) -> str | None:
        self.asked.append(name)
        return self.typed

    def show_data(self, name: str, lines: list[str]) -> None:
        self.shown.append((name, lines))

    def start_check(
        self, task: Callable[[], list[str]], on_done: Callable[[list[str]], None]
    ) -> None:
        self.checks += 1
        on_done(task())

    def show_error(self, message: str) -> None:
        self.errors.append(message)


def provider(
    key_source: str = "stored", models_method: str = "v1", credit_method: str = "none"
) -> Provider:
    return Provider(
        id="deepseek",
        name="DeepSeek",
        base_url=URL,
        key_source=key_source,
        tiers=["m"],
        models_method=models_method,
        credit_method=credit_method,
    )


def make(
    *,
    had_key: bool = False,
    key_source: str = "stored",
    saved: str = "sk-saved",
    models_method: str = "v1",
    credit_method: str = "none",
) -> tuple[ProviderFormPresenter, FakeForm]:
    store = ProviderStore(FakeVault())
    store.add(provider())
    if had_key:
        store.set_key("deepseek", saved)
    form = FakeForm()
    edit = ProviderEdit(provider(key_source, models_method, credit_method), had_key)
    return ProviderFormPresenter(form, store, edit), form


# -- the key button ---------------------------------------------------------------------------


def test_a_provider_without_a_key_offers_to_add_one() -> None:
    _presenter, form = make()
    assert form.key_button == ("Add a ke&y", True)
    assert not form.check_button  # it needs a key to ask


def test_a_provider_with_a_key_offers_to_remove_it() -> None:
    _presenter, form = make(had_key=True)
    assert form.key_button == ("Remove the ke&y", True)
    assert form.check_button


def test_adding_a_key_holds_it_for_the_form_and_changes_the_buttons() -> None:
    presenter, form = make()
    form.typed = "  sk-new "
    presenter.toggle_key("DeepSeek")
    assert form.asked == ["DeepSeek"]
    assert presenter.edit.key == "sk-new"
    assert presenter.edit.has_key
    assert form.key_button == ("Remove the ke&y", True)
    assert form.check_button


def test_a_key_that_is_cancelled_or_empty_is_not_held() -> None:
    presenter, form = make()
    form.typed = None
    presenter.toggle_key("DeepSeek")
    form.typed = "  "
    presenter.toggle_key("DeepSeek")
    assert not presenter.edit.has_key
    assert form.errors == ["The key is empty."]  # only the empty one is an error


def test_removing_the_saved_key_is_held_until_the_form_is_accepted() -> None:
    presenter, form = make(had_key=True)
    presenter.toggle_key("DeepSeek")
    assert presenter.edit.remove_key
    assert not presenter.edit.has_key
    assert form.key_button == ("Add a ke&y", True)
    form.typed = "sk-again"
    presenter.toggle_key("DeepSeek")  # a key added after the removal: the saved one is replaced
    assert presenter.edit.key == "sk-again"
    assert not presenter.edit.remove_key


def test_removing_a_key_typed_in_the_form_forgets_it() -> None:
    presenter, form = make()
    form.typed = "sk-new"
    presenter.toggle_key("DeepSeek")
    presenter.toggle_key("DeepSeek")
    assert presenter.edit.key == ""
    assert not presenter.edit.remove_key  # there was no saved key to remove
    assert form.key_button == ("Add a ke&y", True)


def test_a_provider_that_needs_no_key_has_no_key_button_and_can_be_checked() -> None:
    presenter, form = make(key_source=KEY_NONE)
    assert form.key_button[1] is False
    assert form.check_button
    presenter.key_source_changed("stored")
    assert form.key_button[1] is True
    assert not form.check_button


# -- the methods ------------------------------------------------------------------------------


def test_with_no_method_at_all_there_is_nothing_to_check() -> None:
    presenter, form = make(had_key=True, models_method="none", credit_method="none")
    assert not form.check_button
    presenter.methods_changed("v1", "none")
    assert form.check_button
    presenter.methods_changed("none", "deepseek")
    assert form.check_button  # the credit alone is enough
    presenter.methods_changed("none", "none")
    assert not form.check_button


def test_an_unknown_method_counts_as_none() -> None:
    _presenter, form = make(had_key=True, models_method="gone", credit_method="gone")
    assert not form.check_button


# -- the check --------------------------------------------------------------------------------


def patch_models(
    monkeypatch: pytest.MonkeyPatch, answer: list[str] | Exception
) -> list[tuple[str, str]]:
    calls: list[tuple[str, str]] = []

    def fake(self: V1Models, base_url: str, key: str = "", **options: object) -> list[str]:
        calls.append((base_url, key))
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(V1Models, "fetch", fake)
    return calls


def patch_credit(
    monkeypatch: pytest.MonkeyPatch, answer: list[str] | Exception
) -> list[tuple[str, str, str]]:
    calls: list[tuple[str, str, str]] = []

    def fake(
        self: DeepSeekCredit, name: str, base_url: str, key: str, **options: object
    ) -> list[str]:
        calls.append((name, base_url, key))
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(DeepSeekCredit, "credit", fake)
    return calls


def test_the_check_shows_the_models_then_the_credit(monkeypatch: pytest.MonkeyPatch) -> None:
    models = patch_models(monkeypatch, ["flash", "pro"])
    credit = patch_credit(monkeypatch, ["DeepSeek: balance 4.99 USD."])
    presenter, form = make(had_key=True, credit_method="deepseek")
    presenter.check_data("DeepSeek", "https://typed.example/anthropic")
    assert models == [("https://typed.example/anthropic", "sk-saved")]
    assert credit == [("DeepSeek", "https://typed.example/anthropic", "sk-saved")]
    assert form.shown == [
        (
            "DeepSeek",
            ["Models: 2.", "flash", "pro", "", "DeepSeek: balance 4.99 USD."],
        )
    ]


def test_a_method_set_to_none_is_left_out(monkeypatch: pytest.MonkeyPatch) -> None:
    models = patch_models(monkeypatch, ["m"])
    credit = patch_credit(monkeypatch, ["x"])
    presenter, form = make(had_key=True, models_method="none", credit_method="deepseek")
    presenter.check_data("DeepSeek", URL)
    assert models == []
    assert form.shown == [("DeepSeek", ["x"])]
    presenter.methods_changed("v1", "none")
    presenter.check_data("DeepSeek", URL)
    assert len(credit) == 1  # not asked the second time
    assert form.shown[-1] == ("DeepSeek", ["Models: 1.", "m"])


def test_a_failure_of_one_method_is_a_line_and_the_other_still_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_models(monkeypatch, ModelListError("The server refused the key (error 401)."))
    patch_credit(monkeypatch, ["DeepSeek: balance 1.00 USD."])
    presenter, form = make(had_key=True, credit_method="deepseek")
    presenter.check_data("DeepSeek", URL)
    assert form.errors == []
    assert form.shown == [
        (
            "DeepSeek",
            [
                "Models not available. The server refused the key (error 401).",
                "",
                "DeepSeek: balance 1.00 USD.",
            ],
        )
    ]


def test_the_credit_failure_is_a_line_of_the_credit_method(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_models(monkeypatch, ["m"])
    patch_credit(monkeypatch, BalanceError("The server refused the key (error 401)."))
    presenter, form = make(had_key=True, credit_method="deepseek")
    presenter.check_data("DeepSeek", URL)
    assert form.shown[0][1][-1] == (
        "DeepSeek: balance not available. The server refused the key (error 401)."
    )


def test_a_key_typed_in_the_form_is_the_one_used(monkeypatch: pytest.MonkeyPatch) -> None:
    models = patch_models(monkeypatch, ["m"])
    presenter, form = make(had_key=True)
    form.typed = "sk-typed"
    presenter.toggle_key("DeepSeek")  # removes the saved one
    presenter.toggle_key("DeepSeek")  # adds the typed one
    presenter.check_data("DeepSeek", URL)
    assert models == [(URL, "sk-typed")]


def test_no_key_is_given_when_none_is_needed(monkeypatch: pytest.MonkeyPatch) -> None:
    models = patch_models(monkeypatch, ["m"])
    presenter, _form = make(key_source=KEY_NONE)
    presenter.check_data("LM Studio", "http://127.0.0.1:1234")
    assert models == [("http://127.0.0.1:1234", "")]


def test_checking_without_a_key_is_told_before_any_request(monkeypatch: pytest.MonkeyPatch) -> None:
    models = patch_models(monkeypatch, ["m"])
    presenter, form = make()
    presenter.check_data("DeepSeek", URL)
    assert form.errors == ["No key is saved for DeepSeek."]
    assert form.checks == 0
    assert models == []
