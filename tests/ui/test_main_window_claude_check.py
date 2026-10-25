"""Tests of the main window: Claude Code missing is said at the start and in the status bar."""

import pytest
import wx
from main_window_support import _runner, _settings

from wxclaude.core.claude.runner import ClaudeRunner
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
