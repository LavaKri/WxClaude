from pathlib import Path

import pytest
import wx
from main_window_support import _runner, _settings

from wxclaude.core.announcements import NullSoundPlayer
from wxclaude.ui.main_window import MainWindow


@pytest.fixture(scope="session")
def wx_app():
    """One wx application for the whole session: wx cannot cleanly recreate it per test."""
    return wx.App()


@pytest.fixture(autouse=True)
def claude_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty Claude Code configuration folder: the tests never read the real one."""
    folder = tmp_path / "claude-config"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(folder))
    return folder


@pytest.fixture(autouse=True)
def silent_sounds(monkeypatch: pytest.MonkeyPatch) -> None:
    """The announcement sounds are never played by the tests."""
    monkeypatch.setattr("wxclaude.ui.feedback.create_sound_player", NullSoundPlayer)


@pytest.fixture
def window(wx_app: wx.App):
    window = MainWindow(_settings(), _runner())
    yield window
    window.Destroy()
    wx.SafeYield()


@pytest.fixture
def conversation(window: MainWindow, tmp_path: Path) -> MainWindow:
    """A window with a workspace and a conversation, as after "New conversation"."""
    window.open_workspace(tmp_path)
    window._conversations.start_new("Notes")
    return window
