from collections.abc import Callable, Iterator
from pathlib import Path
from typing import TypeVar

import pytest
import wx
from main_window_support import _runner, _settings

from wxclaude.core.speech.announcements import NullSoundPlayer
from wxclaude.ui.main_window import MainWindow

_Window = TypeVar("_Window", bound=wx.Window)


@pytest.fixture(scope="session")
def wx_app():
    """One wx application for the whole session: wx cannot cleanly recreate it per test."""
    return wx.App()


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
def destroy_after(wx_app: wx.App) -> Iterator[Callable[[_Window], _Window]]:
    """Give a window made by the test; it is destroyed after the test, even when it fails.

    A window the test already destroyed is left alone.
    """
    windows: list[wx.Window] = []

    def keep(window: _Window) -> _Window:
        windows.append(window)
        return window

    yield keep
    for window in reversed(windows):
        if window:  # False once wx has deleted it
            window.Destroy()
    wx.SafeYield()


@pytest.fixture
def conversation(window: MainWindow, tmp_path: Path) -> MainWindow:
    """A window with a workspace and a conversation, as after "New conversation"."""
    window.open_workspace(tmp_path)
    window._conversations.start_new("Notes")
    return window
