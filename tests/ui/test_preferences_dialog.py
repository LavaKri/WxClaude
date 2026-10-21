import pytest
import wx

from wxclaude.core.agents import DEFAULT_AGENT, Agent
from wxclaude.core.settings import Settings
from wxclaude.core.shortcuts import INTERRUPT_COMMAND, ShortcutProblem
from wxclaude.ui.preferences_dialog import PreferencesDialog

pytestmark = pytest.mark.ui


@pytest.fixture
def settings() -> Settings:
    return Settings.load(None)


@pytest.fixture
def dialog(wx_app: wx.App, settings: Settings):
    dialog = PreferencesDialog(None, settings)
    yield dialog
    dialog.Destroy()
    wx.SafeYield()  # a dialog is deleted when the application is idle


def test_tabs_are_in_the_expected_order(dialog: PreferencesDialog) -> None:
    notebook = dialog._notebook
    assert notebook.GetPageCount() == 6
    assert [notebook.GetPageText(index) for index in range(6)] == [
        "General",
        "Claude",
        "Workspace",
        "Agent",
        "Shortcuts",
        "Screen reader",
    ]


def test_the_new_options_are_checked_by_default_and_can_be_changed(
    dialog: PreferencesDialog, settings: Settings
) -> None:
    assert dialog._hide_system_messages.GetValue()
    assert dialog._announce_progress.GetValue()
    assert not dialog._local_tools_only.GetValue()
    dialog._hide_system_messages.SetValue(False)
    dialog._announce_progress.SetValue(False)
    dialog._local_tools_only.SetValue(True)
    dialog.apply(settings)
    assert (settings.hide_system_messages, settings.announce_progress) == (False, False)
    assert settings.local_tools_only


def test_agent_edits_survive_switching_between_the_two_agents(
    dialog: PreferencesDialog, settings: Settings
) -> None:
    dialog._agent_panel._model.SetSelection(2)  # opus (no "not set" entry here)
    dialog._agent_list.SetSelection(1)
    dialog._on_agent_chosen(wx.CommandEvent())
    assert dialog._agent_panel.agent == settings.alternative_agent
    dialog._agent_list.SetSelection(0)
    dialog._on_agent_chosen(wx.CommandEvent())
    assert dialog._agent_panel.agent.model == "opus"
    dialog.apply(settings)
    assert settings.default_agent.model == "opus"
    assert settings.alternative_agent == Agent(effort="low")


def test_the_agent_of_a_conversation_has_no_unset_entry_but_the_alternative_has(
    dialog: PreferencesDialog,
) -> None:
    panel = dialog._agent_panel
    assert panel._model.GetCount() == 4  # haiku, sonnet, opus, fable
    assert panel.agent == DEFAULT_AGENT
    dialog._agent_list.SetSelection(1)
    dialog._on_agent_chosen(wx.CommandEvent())
    assert panel._model.GetCount() == 5
    assert panel._model.GetString(0) == "(same as the conversation)"
    assert panel.agent.model is None
    assert panel.agent.effort == "low"


def test_a_shortcut_can_be_assigned_and_applied(
    dialog: PreferencesDialog, settings: Settings
) -> None:
    assert dialog.assign_shortcut(INTERRUPT_COMMAND, "Ctrl+K").problem is None
    dialog.apply(settings)
    assert settings.shortcut_for(INTERRUPT_COMMAND) == "Ctrl+K"


def test_the_screen_reader_output_can_be_chosen(
    dialog: PreferencesDialog, settings: Settings
) -> None:
    dialog.output_choice.SetSelection(0)  # "No output" is always the first
    dialog.apply(settings)
    assert settings.screen_reader_output == "none"


def test_a_taken_shortcut_is_refused(dialog: PreferencesDialog) -> None:
    check = dialog.assign_shortcut(INTERRUPT_COMMAND, "Ctrl+N")
    assert check.problem is ShortcutProblem.TAKEN


def test_claude_is_searched_automatically_by_default_and_the_path_is_greyed(
    dialog: PreferencesDialog,
) -> None:
    assert dialog.claude_auto_search.GetValue()
    assert not dialog.claude_path.IsEnabled()
    assert not dialog.claude_browse.IsEnabled()
    dialog.claude_auto_search.SetValue(False)
    dialog._update_claude_path()
    assert dialog.claude_path.IsEnabled()
    assert dialog.claude_browse.IsEnabled()


def test_the_claude_path_is_applied_to_the_settings(
    dialog: PreferencesDialog, settings: Settings
) -> None:
    dialog.claude_auto_search.SetValue(False)
    dialog.claude_path.SetValue("  C:/tools/claude.exe ")
    dialog.apply(settings)
    assert not settings.claude_auto_search
    assert settings.claude_path == "C:/tools/claude.exe"


def test_ok_is_refused_for_a_manual_path_that_is_not_a_file(
    dialog: PreferencesDialog, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shown: list[str] = []

    class Warning:
        def __init__(self, _parent, message, *_args) -> None:
            shown.append(message)

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def ShowModal(self) -> int:  # noqa: N802
            return wx.ID_OK

    monkeypatch.setattr(wx, "MessageDialog", Warning)
    dialog.claude_auto_search.SetValue(False)
    dialog.claude_path.SetValue("")
    event = wx.CommandEvent(wx.wxEVT_BUTTON, wx.ID_OK)
    skipped: list[bool] = []
    event.Skip = lambda *_a: skipped.append(True)  # type: ignore[method-assign]
    dialog._on_ok(event)
    assert skipped == []
    assert dialog._notebook.GetSelection() == 1
    assert shown == ["Give the path of claude-p, or turn the automatic search on."]
    claude = tmp_path / "claude.exe"
    claude.write_text("", encoding="utf-8")
    dialog.claude_path.SetValue(str(claude))
    dialog._on_ok(event)
    assert skipped == [True]
