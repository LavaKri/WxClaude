import pytest
import wx

from wxclaude.core.agents import Agent
from wxclaude.core.settings import Settings
from wxclaude.ui.main_window import MainWindow

pytestmark = pytest.mark.ui


@pytest.fixture
def window():
    app = wx.App()
    settings = Settings.load(None)
    settings.default_agent = Agent(model="opus", effort="high")
    window = MainWindow(settings)
    yield window
    window.Destroy()
    del app


def test_main_window_can_be_created(window: MainWindow) -> None:
    assert window.GetTitle() == "WxClaude"


def test_alternative_agent_overrides_only_what_it_sets(window: MainWindow) -> None:
    assert window.agent_for(alternative=False) == Agent(model="opus", effort="high")
    assert window.agent_for(alternative=True) == Agent(model="opus", effort="low")


def test_send_prompt_echoes_and_clears_the_prompt(window: MainWindow) -> None:
    window._prompt.SetValue("hello")
    window.send_prompt(alternative=False)
    assert "hello" in window._conversation.GetValue()
    assert window._prompt.GetValue() == ""
