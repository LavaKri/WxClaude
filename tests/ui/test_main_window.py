import sys
from pathlib import Path

import pytest
import wx

from wxclaude.core.agents import Agent
from wxclaude.core.conversations import is_conversation_id, new_conversation_id
from wxclaude.core.settings import Settings
from wxclaude.ui.main_window import MainWindow
from wxclaude.ui.message_sinks import create_sink

pytestmark = pytest.mark.ui


def _settings() -> Settings:
    settings = Settings.load(None)
    settings.default_agent = Agent(model="opus", effort="high")
    settings.screen_reader_output = "none"  # UI Automation is tested on its own below
    return settings


@pytest.fixture
def window(wx_app: wx.App):
    window = MainWindow(_settings())
    yield window
    window.Destroy()
    wx.SafeYield()


@pytest.fixture
def conversation(window: MainWindow, tmp_path: Path) -> MainWindow:
    """A window with a workspace and a conversation, as after "New conversation"."""
    window.open_workspace(tmp_path)
    window._start_new_conversation("Notes")
    return window


def _enabled(items: list[wx.MenuItem]) -> list[bool]:
    return [item.IsEnabled() for item in items]


def test_at_the_first_start_there_is_no_workspace_and_no_conversation(window: MainWindow) -> None:
    assert window.GetTitle() == "WxClaude"
    assert window.conversation_id == ""
    assert not window.can_send
    assert not window._prompt.IsEnabled()
    assert not any(_enabled(window._needs_workspace))
    assert not any(_enabled(window._needs_conversation))
    assert not window._interrupt_item.IsEnabled()
    assert not window._recent_item.IsEnabled()  # nothing opened yet


def test_a_workspace_without_conversation_only_allows_to_start_one(
    window: MainWindow, tmp_path: Path
) -> None:
    window.open_workspace(tmp_path)
    assert window.GetTitle() == f"{tmp_path.name} - WxClaude"
    assert all(_enabled(window._needs_workspace))
    assert not any(_enabled(window._needs_conversation))
    assert not window.can_send


def test_a_conversation_enables_everything_that_needs_one(conversation: MainWindow) -> None:
    assert all(_enabled(conversation._needs_workspace))
    assert all(_enabled(conversation._needs_conversation))
    assert conversation._prompt.IsEnabled()
    assert conversation.can_send
    assert is_conversation_id(conversation.conversation_id)
    assert conversation._settings.last_conversation_id == conversation.conversation_id


def test_another_workspace_closes_the_conversation(
    conversation: MainWindow, tmp_path: Path
) -> None:
    other = tmp_path / "other"
    other.mkdir()
    conversation.open_workspace(other)
    assert conversation.conversation_id == ""
    assert conversation._settings.last_conversation_id == ""
    assert not any(_enabled(conversation._needs_conversation))
    assert not conversation._prompt.IsEnabled()


def test_the_same_workspace_keeps_the_conversation(
    conversation: MainWindow, tmp_path: Path
) -> None:
    identifier = conversation.conversation_id
    conversation.open_workspace(tmp_path)
    assert conversation.conversation_id == identifier


def test_the_last_workspace_is_opened_and_its_conversation_selected(
    wx_app: wx.App, tmp_path: Path
) -> None:
    settings = _settings()
    settings.last_workspace = str(tmp_path)
    settings.last_conversation_id = new_conversation_id()
    settings.last_conversation_name = "Notes"
    previous = settings.last_conversation_id
    reopened = MainWindow(settings)
    assert reopened.GetTitle() == f"Notes - {tmp_path.name} - WxClaude"
    assert reopened.conversation_id == previous
    assert reopened.can_send
    reopened.Destroy()
    wx.SafeYield()


def test_without_the_option_nothing_is_opened(wx_app: wx.App, tmp_path: Path) -> None:
    settings = _settings()
    settings.reopen_last = False
    settings.last_workspace = str(tmp_path)
    settings.last_conversation_id = new_conversation_id()
    settings.last_conversation_name = "Notes"
    fresh = MainWindow(settings)
    assert fresh.GetTitle() == "WxClaude"
    assert fresh.conversation_id == ""
    fresh.Destroy()
    wx.SafeYield()


def test_a_workspace_that_no_longer_exists_is_not_opened(wx_app: wx.App, tmp_path: Path) -> None:
    settings = _settings()
    settings.last_workspace = str(tmp_path / "gone")
    settings.last_conversation_id = new_conversation_id()
    settings.last_conversation_name = "Notes"
    fresh = MainWindow(settings)
    assert fresh.GetTitle() == "WxClaude"
    assert fresh.conversation_id == ""
    assert not any(_enabled(fresh._needs_workspace))
    fresh.Destroy()
    wx.SafeYield()


def test_the_send_buttons_show_their_shortcuts(window: MainWindow) -> None:
    assert window._send_button.GetLabel() == "&Send (Ctrl+Enter)"
    assert window._alternative_button.GetLabel().endswith("(Shift+Enter)")


def test_alternative_agent_overrides_only_what_it_sets(window: MainWindow) -> None:
    assert window.agent_for(alternative=False) == Agent(model="opus", effort="high")
    assert window.agent_for(alternative=True) == Agent(model="opus", effort="low")


@pytest.mark.skipif(sys.platform != "win32", reason="UI Automation exists only on Windows")
def test_a_ui_automation_notification_can_be_raised(window: MainWindow) -> None:
    sink = create_sink("uia", window)
    sink.show("hello")
    sink.close()


def test_send_prompt_echoes_and_clears_the_prompt(conversation: MainWindow) -> None:
    conversation._prompt.SetValue("hello")
    conversation.send_prompt(alternative=False)
    assert "hello" in conversation._conversation.GetValue()
    assert conversation._prompt.GetValue() == ""


def test_nothing_is_sent_without_a_conversation(window: MainWindow) -> None:
    window._prompt.SetValue("hello")
    window.send_prompt(alternative=False)
    assert window._conversation.GetValue() == ""
