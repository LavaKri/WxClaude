import pytest
import wx

from wxclaude.core.agents import DEFAULT_AGENT, Agent
from wxclaude.core.settings import Settings
from wxclaude.core.shortcuts import INTERRUPT_COMMAND, ShortcutProblem
from wxclaude.ui.options_dialog import OptionsDialog

pytestmark = pytest.mark.ui


@pytest.fixture
def settings() -> Settings:
    return Settings.load(None)


@pytest.fixture
def dialog(wx_app: wx.App, settings: Settings):
    dialog = OptionsDialog(None, settings)
    yield dialog
    dialog.Destroy()
    wx.SafeYield()  # a dialog is deleted when the application is idle


def test_tabs_are_in_the_expected_order(dialog: OptionsDialog) -> None:
    notebook = dialog._notebook
    assert notebook.GetPageCount() == 5
    assert [notebook.GetPageText(index) for index in range(5)] == [
        "General",
        "Conversation",
        "Agent",
        "Shortcuts",
        "Screen reader",
    ]


def test_the_new_options_are_checked_by_default_and_can_be_changed(
    dialog: OptionsDialog, settings: Settings
) -> None:
    assert dialog._hide_system_messages.GetValue()
    assert dialog._announce_progress.GetValue()
    dialog._hide_system_messages.SetValue(False)
    dialog._announce_progress.SetValue(False)
    dialog.apply(settings)
    assert (settings.hide_system_messages, settings.announce_progress) == (False, False)


def test_agent_edits_survive_switching_between_the_two_agents(
    dialog: OptionsDialog, settings: Settings
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
    dialog: OptionsDialog,
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


def test_a_shortcut_can_be_assigned_and_applied(dialog: OptionsDialog, settings: Settings) -> None:
    assert dialog.assign_shortcut(INTERRUPT_COMMAND, "Ctrl+K").problem is None
    dialog.apply(settings)
    assert settings.shortcut_for(INTERRUPT_COMMAND) == "Ctrl+K"


def test_the_screen_reader_output_can_be_chosen(dialog: OptionsDialog, settings: Settings) -> None:
    dialog.output_choice.SetSelection(0)  # "No output" is always the first
    dialog.apply(settings)
    assert settings.screen_reader_output == "none"


def test_a_taken_shortcut_is_refused(dialog: OptionsDialog) -> None:
    check = dialog.assign_shortcut(INTERRUPT_COMMAND, "Ctrl+N")
    assert check.problem is ShortcutProblem.TAKEN
