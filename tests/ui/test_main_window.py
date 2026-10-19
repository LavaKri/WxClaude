import sys

import pytest
import wx

from wxclaude.core.agents import Agent
from wxclaude.core.settings import Settings
from wxclaude.ui.main_window import MainWindow
from wxclaude.ui.message_sinks import create_sink

pytestmark = pytest.mark.ui


@pytest.fixture
def window(wx_app: wx.App):
    settings = Settings.load(None)
    settings.default_agent = Agent(model="opus", effort="high")
    settings.screen_reader_output = "none"  # UI Automation is tested on its own below
    window = MainWindow(settings)
    yield window
    window.Destroy()


def test_main_window_can_be_created(window: MainWindow) -> None:
    assert window.GetTitle() == "WxClaude"


def test_alternative_agent_overrides_only_what_it_sets(window: MainWindow) -> None:
    assert window.agent_for(alternative=False) == Agent(model="opus", effort="high")
    assert window.agent_for(alternative=True) == Agent(model="opus", effort="low")


@pytest.mark.skipif(sys.platform != "win32", reason="UI Automation exists only on Windows")
def test_a_ui_automation_notification_can_be_raised(window: MainWindow) -> None:
    sink = create_sink("uia", window)
    sink.show("hello")
    sink.close()


def test_send_prompt_echoes_and_clears_the_prompt(window: MainWindow) -> None:
    window._prompt.SetValue("hello")
    window.send_prompt(alternative=False)
    assert "hello" in window._conversation.GetValue()
    assert window._prompt.GetValue() == ""
