import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import TypeVar

import pytest
import wx
from main_window_support import _runner, _settings

from wxclaude.core.speech.announcements import NullSoundPlayer
from wxclaude.presenters.security_presenter import SecurityPresenter
from wxclaude.ui.main_window import MainWindow

_Window = TypeVar("_Window", bound=wx.Window)


@pytest.fixture(scope="session")
def wx_app() -> wx.App:
    """One wx application for the whole session: wx cannot cleanly recreate it per test."""
    return wx.App()


#: The names of the threads of ``ui/worker.run_in_background``.
BACKGROUND_THREADS = {"claude-login-check", "provider-check", "provider-balances"}


@pytest.fixture(scope="session", autouse=True)
def finish_background_work(wx_app: wx.App) -> Iterator[None]:
    """At the end of the session, wait for the work still running in the background.

    A window made by the last test may have started one (the check of the login of Claude): its
    thread hands the result over with ``wx.CallAfter``, which fails once the application is gone.
    The fixture needs ``wx_app`` so that it is torn down before it. The windows are destroyed by
    then: nothing is delivered to them. There is no wait after each test, which would make every
    window wait for its thread.
    """
    yield
    deadline = time.monotonic() + 10
    for thread in threading.enumerate():
        if thread.name in BACKGROUND_THREADS:
            thread.join(max(deadline - time.monotonic(), 0))
    wx.SafeYield()


@pytest.fixture(autouse=True)
def silent_sounds(monkeypatch: pytest.MonkeyPatch) -> None:
    """The announcement sounds are never played by the tests."""
    monkeypatch.setattr("wxclaude.ui.feedback.create_sound_player", NullSoundPlayer)


@pytest.fixture(autouse=True)
def folders_are_trusted(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """No offer to approve a folder opens a modal dialog during a test, and a folder is not
    restricted, as before the trust of folders existed. The tests of that feature opt out with
    the marker ``real_security``."""
    if request.node.get_closest_marker("real_security"):
        return
    monkeypatch.setattr(SecurityPresenter, "greet", lambda self: None)
    monkeypatch.setattr(SecurityPresenter, "restricted", property(lambda self: False))


@pytest.fixture
def window(wx_app: wx.App) -> Iterator[MainWindow]:
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
