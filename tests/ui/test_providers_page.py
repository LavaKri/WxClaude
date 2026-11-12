"""The Providers page of the Preferences, the provider dialogs and the list Provider of an agent."""

from collections.abc import Iterator
from pathlib import Path

import pytest
import wx
from fake_vault import FakeVault

from wxclaude.core.config import key_transmission
from wxclaude.core.config.agents import Agent
from wxclaude.core.config.provider_methods import V1Models
from wxclaude.core.config.providers import KEY_NONE, Provider, ProviderStore
from wxclaude.core.config.settings import Settings
from wxclaude.presenters.provider_form_presenter import ProviderEdit
from wxclaude.ui.agent_dialog import AgentDialog
from wxclaude.ui.agent_panel import AgentPanel
from wxclaude.ui.preferences_dialog import PreferencesDialog
from wxclaude.ui.provider_dialogs import KeyDialog, ProviderDialog
from wxclaude.ui.providers_page import ProvidersPage

pytestmark = pytest.mark.ui


def deepseek() -> Provider:
    return Provider(
        id="deepseek",
        name="DeepSeek",
        base_url="https://api.deepseek.com/anthropic",
        tiers=["deepseek-chat", "haiku"],
        send_effort=False,
    )


@pytest.fixture
def store(tmp_path: Path) -> ProviderStore:
    path = tmp_path / "providers.json"
    path.write_text(
        '{"providers": []}', encoding="utf-8"
    )  # a user who has none (not a first start)
    providers = ProviderStore.load(path, FakeVault())
    providers.add(deepseek())
    providers.set_key("deepseek", "sk-1")
    return providers


@pytest.fixture
def settings() -> Settings:
    return Settings.load(None)


@pytest.fixture
def page(wx_app: wx.App, store: ProviderStore, settings: Settings) -> Iterator[ProvidersPage]:
    frame = wx.Frame(None)
    window = ProvidersPage(frame, store, settings)
    yield window
    frame.Destroy()
    wx.SafeYield()


# -- the page -------------------------------------------------------------------------------


def test_the_page_lists_the_providers_with_their_state(page: ProvidersPage) -> None:
    assert list(page._list.GetStrings()) == [
        "Claude, built in",
        "DeepSeek, https://api.deepseek.com/anthropic, key saved",
    ]
    assert page._list.GetSelection() == 0


def test_the_page_has_no_button_for_the_key_nor_for_the_models(page: ProvidersPage) -> None:
    for name in ("_set_key", "_remove_key", "_models", "_test", "_state"):
        assert not hasattr(page, name)  # they are in the form of the provider


def test_the_buttons_follow_the_selection(page: ProvidersPage) -> None:
    for button in (page._edit, page._delete):
        assert not button.IsEnabled()  # Claude: nothing to change
    assert page._add.IsEnabled()
    page._list.SetSelection(1)
    page._on_select(wx.CommandEvent())
    for button in (page._edit, page._delete):
        assert button.IsEnabled()


def test_deleting_asks_first(
    page: ProvidersPage, store: ProviderStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    page._list.SetSelection(1)
    page._on_select(wx.CommandEvent())
    monkeypatch.setattr(page, "confirm_delete", lambda name: False)
    page._act(page.presenter.delete)
    assert store.get("deepseek").name == "DeepSeek"
    monkeypatch.setattr(page, "confirm_delete", lambda name: True)
    page._act(page.presenter.delete)
    assert [p.id for p in store.providers()] == ["claude"]
    assert list(page._list.GetStrings()) == ["Claude, built in"]


def test_a_new_provider_is_added_through_the_form(
    page: ProvidersPage, store: ProviderStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    local = Provider(
        id="",
        name="LM Studio",
        base_url="http://127.0.0.1:1234",
        key_source=KEY_NONE,
        tiers=["qwen"],
    )
    monkeypatch.setattr(page, "ask_provider", lambda edit: ProviderEdit(local))
    page._act(page.presenter.add)
    assert store.get("lm-studio").base_url == "http://127.0.0.1:1234"
    assert page._list.GetSelection() == 2


def test_the_transmission_of_the_key_is_masked_by_default_and_explained(
    page: ProvidersPage,
) -> None:
    assert page.transmission == key_transmission.MASKED
    assert list(page._transmission.GetStrings()) == ["Masked", "Shared", "Relayed"]
    assert "hides it from its models and tools" in page._explanation.GetValue()
    page._transmission.SetSelection(1)
    page._show_explanation()
    assert page.transmission == key_transmission.SHARED
    assert "visible to all the models and tools" in page._explanation.GetValue()
    page._transmission.SetSelection(2)
    page._show_explanation()
    assert page.transmission == key_transmission.RELAYED
    assert "throw-away token" in page._explanation.GetValue()


def test_the_transmission_of_the_key_is_a_setting_stored_with_ok(
    wx_app: wx.App, store: ProviderStore
) -> None:
    settings = Settings.load(None)
    dialog = PreferencesDialog(None, settings, store)
    try:
        assert dialog.providers.transmission == key_transmission.MASKED  # the setting is on
        dialog.providers._transmission.SetSelection(2)
        dialog.apply(settings)
        assert settings.key_transmission == key_transmission.RELAYED
    finally:
        dialog.Destroy()
        wx.SafeYield()


def test_the_page_starts_on_the_transmission_that_is_set(
    wx_app: wx.App, store: ProviderStore
) -> None:
    settings = Settings.load(None)
    settings.key_transmission = key_transmission.SHARED
    frame = wx.Frame(None)
    try:
        assert ProvidersPage(frame, store, settings).transmission == key_transmission.SHARED
    finally:
        frame.Destroy()
        wx.SafeYield()


def test_the_claude_page_no_longer_has_the_scrub(wx_app: wx.App, store: ProviderStore) -> None:
    dialog = PreferencesDialog(None, Settings.load(None), store)
    try:
        assert not hasattr(dialog.claude, "scrub")
    finally:
        dialog.Destroy()
        wx.SafeYield()


def test_the_preferences_hold_the_page_after_the_claude_page(
    wx_app: wx.App, store: ProviderStore
) -> None:
    dialog = PreferencesDialog(None, Settings.load(None), store)
    try:
        notebook = dialog._notebook
        names = [notebook.GetPageText(i) for i in range(notebook.GetPageCount())]
        assert names[:3] == ["General", "Claude", "Providers"]
        assert isinstance(dialog.providers, ProvidersPage)
    finally:
        dialog.Destroy()
        wx.SafeYield()


# -- the form of a provider -------------------------------------------------------------------


def test_the_form_describes_the_provider_it_was_given(wx_app: wx.App, store: ProviderStore) -> None:
    dialog = ProviderDialog(None, store, ProviderEdit(deepseek(), had_key=True))
    try:
        result = dialog.result
        assert result.provider == deepseek()
        assert result.had_key
        assert result.key == ""
        assert not result.remove_key
    finally:
        dialog.Destroy()


def _edit(dialog: ProviderDialog, index: int, text: str) -> None:
    """Choose the line ``index`` of the list *Variable* and type ``text`` as its value."""
    dialog._variable.SetSelection(index)
    dialog._show_variable()
    dialog._value.SetValue(text)


def test_the_form_has_one_list_of_the_models_and_the_variables(
    wx_app: wx.App, store: ProviderStore
) -> None:
    dialog = ProviderDialog(None, store, None)
    try:
        assert dialog._variable.GetName() == "Variable"
        assert [dialog._variable.GetString(i) for i in range(dialog._variable.GetCount())] == [
            "Small model = (as the weakest model given)",
            "Medium model = (as the weakest model given)",
            "Large model = (as the weakest model given)",
            "Largest model = (as the weakest model given)",
            "API_TIMEOUT_MS = (not set)",
            "CLAUDE_CODE_MAX_CONTEXT_TOKENS = (not set)",
            "CLAUDE_CODE_AUTO_COMPACT_WINDOW = (not set)",
            "CLAUDE_CODE_MAX_OUTPUT_TOKENS = (not set)",
        ]
        assert dialog._value.GetName() == "Value of Small model"
        assert "haiku" in dialog._explanation.GetValue()
        assert dialog.result.provider.tiers == []  # nothing typed: the presenter refuses it
    finally:
        dialog.Destroy()


def test_choosing_a_line_shows_its_value_its_limit_and_its_explanation(
    wx_app: wx.App, store: ProviderStore
) -> None:
    given = deepseek()
    given.env = {"API_TIMEOUT_MS": "600000"}
    dialog = ProviderDialog(None, store, ProviderEdit(given, had_key=True))
    try:
        dialog._variable.SetSelection(4)
        dialog._show_variable()
        assert dialog._value.GetValue() == "600000"
        assert dialog._value.GetName() == "Value of API_TIMEOUT_MS"
        assert "response headers" in dialog._explanation.GetValue()
        dialog._variable.SetSelection(0)
        dialog._show_variable()
        assert dialog._value.GetValue() == "deepseek-chat"
    finally:
        dialog.Destroy()


def test_the_line_shows_the_new_value_when_the_field_is_left(
    wx_app: wx.App, store: ProviderStore
) -> None:
    dialog = ProviderDialog(None, store, None)
    try:
        _edit(dialog, 5, "65536")
        assert dialog._variable.GetString(5) == "CLAUDE_CODE_MAX_CONTEXT_TOKENS = (not set)"
        dialog._value.GetEventHandler().ProcessEvent(wx.FocusEvent(wx.wxEVT_KILL_FOCUS))
        assert dialog._variable.GetString(5) == "CLAUDE_CODE_MAX_CONTEXT_TOKENS = 65536"
        assert dialog._variable.GetSelection() == 5  # the selection is kept
    finally:
        dialog.Destroy()


def test_the_variables_come_out_in_the_result(wx_app: wx.App, store: ProviderStore) -> None:
    dialog = ProviderDialog(None, store, None)
    try:
        _edit(dialog, 4, " 600000 ")
        assert dialog.result.provider.env == {"API_TIMEOUT_MS": "600000"}
    finally:
        dialog.Destroy()


def test_an_empty_form_describes_an_empty_provider_to_fill(
    wx_app: wx.App, store: ProviderStore
) -> None:
    dialog = ProviderDialog(None, store, None)
    try:
        dialog._name.SetValue("  Mine ")
        dialog._address.SetValue("http://x")
        _edit(dialog, 1, " b ")
        _edit(dialog, 3, "big")
        provider = dialog.result.provider
        assert (provider.id, provider.name, provider.base_url) == ("", "Mine", "http://x")
        assert provider.tiers == ["b", "b", "b", "big"]  # the weakest given fills the empty ones
        assert provider.models == ["b", "big"]
        assert provider.send_effort
        assert provider.key_source == "stored"
    finally:
        dialog.Destroy()


def test_the_key_button_follows_the_key_of_the_provider(
    wx_app: wx.App, store: ProviderStore
) -> None:
    without = ProviderDialog(None, store, None)
    with_key = ProviderDialog(None, store, ProviderEdit(deepseek(), had_key=True))
    try:
        assert without._key_button.GetLabel() == "Add a ke&y"
        assert not without._check_button.IsEnabled()  # a key is needed to ask
        assert with_key._key_button.GetLabel() == "Remove the ke&y"
        assert with_key._check_button.IsEnabled()
    finally:
        without.Destroy()
        with_key.Destroy()


def test_a_key_typed_in_the_form_comes_out_in_the_result(
    wx_app: wx.App, store: ProviderStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    dialog = ProviderDialog(None, store, None)
    try:
        monkeypatch.setattr(dialog, "ask_key", lambda name: " sk-new ")
        dialog._name.SetValue("Mine")
        dialog.presenter.toggle_key("Mine")
        assert dialog._key_button.GetLabel() == "Remove the ke&y"
        assert dialog.result.key == "sk-new"
        dialog._key_source.SetSelection(1)  # no key needed: the typed key is dropped
        dialog.presenter.key_source_changed("none")
        assert dialog.result.key == ""
        assert not dialog._key_button.IsEnabled()
    finally:
        dialog.Destroy()


def test_removing_the_saved_key_comes_out_in_the_result(
    wx_app: wx.App, store: ProviderStore
) -> None:
    dialog = ProviderDialog(None, store, ProviderEdit(deepseek(), had_key=True))
    try:
        dialog.presenter.toggle_key("DeepSeek")
        assert dialog.result.remove_key
        assert dialog._key_button.GetLabel() == "Add a ke&y"
    finally:
        dialog.Destroy()


def test_the_two_method_lists_start_from_the_provider_and_come_out_in_the_result(
    wx_app: wx.App, store: ProviderStore
) -> None:
    empty = ProviderDialog(None, store, None)
    chosen = ProviderDialog(None, store, ProviderEdit(deepseek(), had_key=True))
    try:
        assert empty.result.provider.models_method == "v1"  # the defaults of a new provider
        assert empty.result.provider.credit_method == "none"
        assert [empty._credit_method.GetString(i) for i in range(2)] == ["No method", "DeepSeek"]
        chosen._credit_method.SetSelection(1)
        chosen.presenter.methods_changed(chosen._models_id, chosen._credit_id)
        assert chosen.result.provider.credit_method == "deepseek"
        chosen._models_method.SetSelection(0)  # None
        assert chosen.result.provider.models_method == "none"
    finally:
        empty.Destroy()
        chosen.Destroy()


def test_the_check_button_needs_a_method_to_ask(wx_app: wx.App, store: ProviderStore) -> None:
    dialog = ProviderDialog(None, store, ProviderEdit(deepseek(), had_key=True))
    try:
        dialog._models_method.SetSelection(0)  # None, and the credit is None too
        dialog.presenter.methods_changed(dialog._models_id, dialog._credit_id)
        assert not dialog._check_button.IsEnabled()
    finally:
        dialog.Destroy()


def test_the_data_are_asked_away_from_the_window_and_shown(
    wx_app: wx.App, store: ProviderStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    dialog = ProviderDialog(None, store, ProviderEdit(deepseek(), had_key=True))
    shown: list[tuple[str, list[str]]] = []
    try:
        # The thread is replaced by a call at once: wx must only be touched by the window thread.
        monkeypatch.setattr(
            "wxclaude.ui.provider_dialogs.run_in_background",
            lambda work, on_done, on_error, **_options: on_done(work()),
        )
        monkeypatch.setattr(dialog, "show_data", lambda name, lines: shown.append((name, lines)))
        monkeypatch.setattr(
            V1Models, "fetch", lambda self, base_url, key="", **options: ["flash", "pro"]
        )
        dialog.presenter.check_data("DeepSeek", "https://x.example")
        assert shown == [("DeepSeek", ["Models: 2.", "flash", "pro"])]
        assert dialog._check_button.IsEnabled()  # enabled again once the answer is back
    finally:
        dialog.Destroy()


def test_the_key_is_typed_hidden_and_can_be_shown(wx_app: wx.App) -> None:
    dialog = KeyDialog(None, "DeepSeek")
    try:
        assert dialog._hidden.IsShown()
        assert not dialog._shown.IsShown()
        dialog._hidden.SetValue("sk-typed")
        assert dialog.key == "sk-typed"
        dialog._show.SetValue(True)
        dialog._swap()
        assert dialog._shown.IsShown()
        assert dialog._shown.GetValue() == "sk-typed"
        dialog._shown.SetValue("sk-edited")
        assert dialog.key == "sk-edited"
        dialog._show.SetValue(False)
        dialog._swap()
        assert dialog.key == "sk-edited"
    finally:
        dialog.Destroy()


# -- the list Provider of an agent ----------------------------------------------------------


def test_the_agent_panel_offers_the_providers_and_their_models(
    wx_app: wx.App, store: ProviderStore
) -> None:
    frame = wx.Frame(None)
    try:
        panel = AgentPanel(frame, Agent("opus", "high", "manual", "claude"), None, providers=store)
        assert list(panel._provider.GetStrings()) == ["Claude", "DeepSeek"]
        assert panel._model.GetCount() == 4  # the models of Claude
        panel._provider.SetSelection(1)
        panel._on_provider(wx.CommandEvent())
        assert list(panel._model.GetStrings()) == ["deepseek-chat", "haiku"]
        assert panel.agent == Agent("deepseek-chat", "high", "manual", "deepseek")
        panel._model.SetSelection(1)  # haiku, which Claude has as well
        panel._provider.SetSelection(0)
        panel._on_provider(wx.CommandEvent())
        assert panel.agent == Agent("haiku", "high", "manual", "claude")
    finally:
        frame.Destroy()
        wx.SafeYield()


def test_an_agent_of_a_provider_that_is_gone_shows_claude(
    wx_app: wx.App, store: ProviderStore
) -> None:
    frame = wx.Frame(None)
    try:
        panel = AgentPanel(frame, Agent("x", "low", "plan", "gone"), None, providers=store)
        assert panel.agent.provider == "claude"
    finally:
        frame.Destroy()
        wx.SafeYield()


def test_the_alternative_agent_can_leave_the_provider_unset(
    wx_app: wx.App, store: ProviderStore
) -> None:
    frame = wx.Frame(None)
    try:
        panel = AgentPanel(frame, Agent(effort="low"), "(same)", providers=store)
        assert list(panel._provider.GetStrings()) == ["(same)", "Claude", "DeepSeek"]
        assert panel.agent == Agent(effort="low")
        panel._provider.SetSelection(2)
        panel._on_provider(wx.CommandEvent())
        assert panel.agent.provider == "deepseek"
        assert panel.agent.model is None  # unset stays unset
        panel._provider.SetSelection(0)
        assert panel.agent.provider is None
    finally:
        frame.Destroy()
        wx.SafeYield()


def test_the_agent_dialog_starts_on_the_provider(wx_app: wx.App, store: ProviderStore) -> None:
    dialog = AgentDialog(None, Agent("opus", "high", "manual", "claude"), store)
    try:
        assert dialog.agent == Agent("opus", "high", "manual", "claude")
        assert dialog._panel._provider.GetName() == "Provider"
    finally:
        dialog.Destroy()
        wx.SafeYield()
