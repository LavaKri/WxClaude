import pytest
import wx

from wxclaude.core.agents import DEFAULT_AGENT, Agent
from wxclaude.core.announcements import CATEGORIES, END_OF_ANSWER, Destination
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
    assert dialog.workspace.hide_system_messages.GetValue()
    assert not dialog.workspace.local_tools_only.GetValue()
    dialog.workspace.hide_system_messages.SetValue(False)
    dialog.workspace.local_tools_only.SetValue(True)
    dialog.apply(settings)
    assert not settings.hide_system_messages
    assert settings.local_tools_only


def test_the_screen_reader_page_lists_the_categories_with_their_default_destination(
    dialog: PreferencesDialog,
) -> None:
    page = dialog.screen_reader
    assert page.category_list.GetItemCount() == len(CATEGORIES)
    assert page.category_list.GetItemText(CATEGORIES.index(END_OF_ANSWER), 1) == "Message.wav"
    assert page.category_list.GetFirstSelected() == 0
    assert page.destination_choice.GetCount() == len(CATEGORIES[0].choices)


def test_a_destination_is_applied_only_with_ok_and_the_default_can_be_restored(
    dialog: PreferencesDialog, settings: Settings
) -> None:
    page = dialog.screen_reader
    page.category_list.Select(CATEGORIES.index(END_OF_ANSWER))
    page.presenter.choose(END_OF_ANSWER.choices.index(Destination.MESSAGE))
    assert page.category_list.GetItemText(CATEGORIES.index(END_OF_ANSWER), 1) == "Message"
    assert settings.destination_for(END_OF_ANSWER) is Destination.SOUND_1  # not yet
    dialog.apply(settings)
    assert settings.destination_for(END_OF_ANSWER) is Destination.MESSAGE
    page.presenter.restore_default()
    dialog.apply(settings)
    assert settings.announcements == {}


def test_agent_edits_survive_switching_between_the_two_agents(
    dialog: PreferencesDialog, settings: Settings
) -> None:
    page = dialog.agent
    page.agent_panel._model.SetSelection(2)  # opus (no "not set" entry here)
    page.agent_list.SetSelection(1)
    page._on_agent_chosen(wx.CommandEvent())
    assert page.agent_panel.agent == settings.alternative_agent
    page.agent_list.SetSelection(0)
    page._on_agent_chosen(wx.CommandEvent())
    assert page.agent_panel.agent.model == "opus"
    dialog.apply(settings)
    assert settings.default_agent.model == "opus"
    assert settings.alternative_agent == Agent(effort="low")


def test_the_agent_of_a_conversation_has_no_unset_entry_but_the_alternative_has(
    dialog: PreferencesDialog,
) -> None:
    panel = dialog.agent.agent_panel
    assert panel._model.GetCount() == 4  # haiku, sonnet, opus, fable
    assert panel.agent == DEFAULT_AGENT
    dialog.agent.agent_list.SetSelection(1)
    dialog.agent._on_agent_chosen(wx.CommandEvent())
    assert panel._model.GetCount() == 5
    assert panel._model.GetString(0) == "(same as the conversation)"
    assert panel.agent.model is None
    assert panel.agent.effort == "low"


def test_a_shortcut_can_be_assigned_and_applied(
    dialog: PreferencesDialog, settings: Settings
) -> None:
    assert dialog.shortcuts.assign_shortcut(INTERRUPT_COMMAND, "Ctrl+K").problem is None
    dialog.apply(settings)
    assert settings.shortcut_for(INTERRUPT_COMMAND) == "Ctrl+K"


def test_the_screen_reader_output_can_be_chosen(
    dialog: PreferencesDialog, settings: Settings
) -> None:
    dialog.screen_reader.output_choice.SetSelection(0)  # "No output" is always the first
    dialog.apply(settings)
    assert settings.screen_reader_output == "none"


def test_a_taken_shortcut_is_refused(dialog: PreferencesDialog) -> None:
    check = dialog.shortcuts.assign_shortcut(INTERRUPT_COMMAND, "Ctrl+N")
    assert check.problem is ShortcutProblem.TAKEN


def test_claude_is_searched_automatically_by_default_and_the_path_is_greyed(
    dialog: PreferencesDialog,
) -> None:
    page = dialog.claude
    assert page.auto_search.GetValue()
    assert not page.path.IsEnabled()
    assert not page.browse.IsEnabled()
    page.auto_search.SetValue(False)
    page._update_path()
    assert page.path.IsEnabled()
    assert page.browse.IsEnabled()


def test_the_claude_path_is_applied_to_the_settings(
    dialog: PreferencesDialog, settings: Settings
) -> None:
    dialog.claude.auto_search.SetValue(False)
    dialog.claude.path.SetValue("  C:/tools/claude.exe ")
    dialog.apply(settings)
    assert not settings.claude_auto_search
    assert settings.claude_path == "C:/tools/claude.exe"


def test_the_permission_channel_is_stdio_by_default_and_the_waiting_time_is_greyed(
    dialog: PreferencesDialog,
) -> None:
    page = dialog.claude
    assert page.channel.GetSelection() == 0
    assert page.channel.GetString(0) == "Stdio protocol"
    assert page.channel.GetString(1) == "HTTP hook"
    assert page.minutes.GetValue() == 10
    assert not page.minutes.IsEnabled()
    page.channel.SetSelection(1)
    page._update_minutes()
    assert page.minutes.IsEnabled()


def test_the_permission_channel_and_the_waiting_time_are_applied_to_the_settings(
    dialog: PreferencesDialog, settings: Settings
) -> None:
    dialog.claude.channel.SetSelection(1)
    dialog.claude.minutes.SetValue(4)
    dialog.apply(settings)
    assert (settings.permission_channel, settings.hook_timeout_minutes) == ("hook", 4)


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
    dialog.claude.auto_search.SetValue(False)
    dialog.claude.path.SetValue("")
    event = wx.CommandEvent(wx.wxEVT_BUTTON, wx.ID_OK)
    skipped: list[bool] = []
    event.Skip = lambda *_a: skipped.append(True)  # type: ignore[method-assign]
    dialog._on_ok(event)
    assert skipped == []
    assert dialog._notebook.GetSelection() == 1
    assert shown == ["Give the path of claude-p, or turn the automatic search on."]
    claude = tmp_path / "claude.exe"
    claude.write_text("", encoding="utf-8")
    dialog.claude.path.SetValue(str(claude))
    dialog._on_ok(event)
    assert skipped == [True]
