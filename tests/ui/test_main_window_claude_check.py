"""Tests of the main window: Claude Code missing is said at the start and in the status bar."""

import time
from collections.abc import Callable
from dataclasses import replace

import pytest
import wx
from main_window_support import _runner, _settings

from wxclaude.core.claude.runner import ClaudeRunner
from wxclaude.core.config.providers import KEY_NONE, Provider
from wxclaude.ui.feedback import Feedback
from wxclaude.ui.main_window import MainWindow

pytestmark = pytest.mark.ui


@pytest.fixture
def confirmations(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """The questions asked to the user, always answered No."""
    asked: list[tuple[str, str]] = []

    def confirm(
        _self: Feedback, title: str, message: str, yes_label: str = "", no_label: str = ""
    ) -> bool:
        asked.append((title, message))
        return False

    monkeypatch.setattr(Feedback, "confirm", confirm)
    return asked


def test_nothing_is_said_when_claude_can_be_started(
    wx_app: wx.App, confirmations: list[tuple[str, str]]
) -> None:
    window = MainWindow(_settings(), _runner())
    try:
        wx.SafeYield()
        assert confirmations == []
        assert window.GetStatusBar().GetStatusText(2) == "Ready"
    finally:
        window.Destroy()
        wx.SafeYield()


def test_a_missing_claude_is_said_once_at_the_start_and_in_the_status_bar(
    wx_app: wx.App, confirmations: list[tuple[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("wxclaude.core.claude.runner.shutil.which", lambda _name: None)
    window = MainWindow(_settings(), ClaudeRunner())
    try:
        wx.SafeYield()
        assert [title for title, _message in confirmations] == ["Claude Code not found"]
        assert window.GetStatusBar().GetStatusText(2) == "Claude Code not found"
    finally:
        window.Destroy()
        wx.SafeYield()


def _wait_for_status(window: MainWindow, text: str) -> None:
    """Let the reading of the login, done in a thread, reach the window."""
    deadline = time.monotonic() + 15
    while window.GetStatusBar().GetStatusText(2) != text:
        assert time.monotonic() < deadline, window.GetStatusBar().GetStatusText(2)
        wx.Yield()
        time.sleep(0.02)


def test_not_logged_in_is_said_in_the_status_bar_and_offered_once_at_the_start(
    wx_app: wx.App, confirmations: list[tuple[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_LOGIN", "out")
    window = MainWindow(_settings(), _runner())
    try:
        _wait_for_status(window, "Not logged in to Claude Code")
        assert [title for title, _message in confirmations] == ["Not logged in to Claude Code"]
    finally:
        window.Destroy()
        wx.SafeYield()


def test_the_offer_opens_the_sign_in_when_the_user_says_yes(
    wx_app: wx.App, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_LOGIN", "out")
    monkeypatch.setattr(Feedback, "confirm", lambda *args, **kwargs: True)
    opened: list[str] = []
    monkeypatch.setattr(MainWindow, "_open_sign_in", lambda self: opened.append("sign in"))
    window = MainWindow(_settings(), _runner())
    try:
        deadline = time.monotonic() + 15
        while not opened:
            assert time.monotonic() < deadline, "the sign-in was not opened"
            wx.Yield()
            time.sleep(0.02)
    finally:
        window.Destroy()
        wx.SafeYield()


class _NoDialog:
    """Stands for the sign-in dialog, which is not shown."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def __enter__(self) -> _NoDialog:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None


def test_the_login_is_read_again_when_the_sign_in_is_closed(
    wx_app: wx.App, confirmations: list[tuple[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_LOGIN", "out")
    monkeypatch.setattr("wxclaude.ui.main_window.LoginDialog", _NoDialog)
    window = MainWindow(_settings(), _runner())
    try:
        _wait_for_status(window, "Not logged in to Claude Code")
        monkeypatch.setattr(window._feedback, "modal", lambda dialog: 0)
        monkeypatch.setenv("FAKE_CLAUDE_LOGIN", "in")  # the user signed in
        window._open_sign_in()
        _wait_for_status(window, "Ready")
        assert len(confirmations) == 1  # the offer was made once, at the start
    finally:
        window.Destroy()
        wx.SafeYield()


@pytest.mark.parametrize(("provider", "readings"), [(None, 1), ("local", 0)])
def test_the_login_is_only_read_when_the_default_agent_uses_claude(
    wx_app: wx.App,
    confirmations: list[tuple[str, str]],
    monkeypatch: pytest.MonkeyPatch,
    provider: str | None,
    readings: int,
) -> None:
    """The reading is a thread: what is checked is that it is started, not what it finds."""
    started: list[str] = []

    def start(
        work: Callable[[], bool | None],
        done: Callable[[bool | None], None],
        failed: Callable[[str], None],
        *,
        name: str,
        alive: Callable[[], bool],
    ) -> None:
        started.append(name)

    monkeypatch.setattr("wxclaude.ui.claude_check_view.run_in_background", start)
    settings = _settings()
    if provider is not None:
        settings.default_agent = replace(settings.default_agent, provider=provider)
    window = MainWindow(settings, _runner())
    if provider is not None:  # added after the window, before the check that it posts for later
        window.providers.add(
            Provider(
                id=provider,
                name="Local",
                base_url="http://localhost:11434",
                key_source=KEY_NONE,
                tiers=["m1", "m2", "m3", "m4"],
            )
        )
    try:
        wx.SafeYield()  # the check of the start
        assert len(started) == readings
        assert confirmations == []
        assert window.GetStatusBar().GetStatusText(2) == "Ready"
    finally:
        window.Destroy()
        wx.SafeYield()


def test_the_ready_line_comes_back_when_claude_is_found_after_the_preferences(
    wx_app: wx.App, confirmations: list[tuple[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("wxclaude.core.claude.runner.shutil.which", lambda _name: None)
    window = MainWindow(_settings(), ClaudeRunner())
    try:
        wx.SafeYield()
        monkeypatch.setattr("wxclaude.core.claude.runner.shutil.which", lambda _name: "/c/claude")
        window._claude_check.check(offer=False)
        assert window.GetStatusBar().GetStatusText(2) == "Ready"
        assert len(confirmations) == 1  # not asked again
    finally:
        window.Destroy()
        wx.SafeYield()
