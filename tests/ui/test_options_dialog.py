import pytest
import wx

from wxclaude.core.agents import Agent
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
    assert notebook.GetPageCount() == 4
    assert notebook.GetPageText(1) == "Agent"
    assert notebook.GetPageText(2) == "Shortcuts"


def test_agent_edits_survive_switching_between_the_two_agents(
    dialog: OptionsDialog, settings: Settings
) -> None:
    dialog._agent_panel._model.SetSelection(3)  # opus
    dialog._agent_list.SetSelection(1)
    dialog._on_agent_chosen(wx.CommandEvent())
    assert dialog._agent_panel.agent == settings.alternative_agent
    dialog._agent_list.SetSelection(0)
    dialog._on_agent_chosen(wx.CommandEvent())
    assert dialog._agent_panel.agent.model == "opus"
    dialog.apply(settings)
    assert settings.default_agent.model == "opus"
    assert settings.alternative_agent == Agent(effort="low")


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
