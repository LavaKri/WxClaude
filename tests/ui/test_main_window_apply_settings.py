"""The settings put to work in the main window: the same steps at the start and after the
Preferences (the output of the announcements, what is displayed, the shortcuts, the claude program).
"""

import pytest
import wx
from main_window_support import _runner, _settings

from wxclaude.core.conversation.messages import Message, Role
from wxclaude.ui.feedback import Feedback
from wxclaude.ui.main_window import MainWindow

pytestmark = pytest.mark.ui

CLAUDE = "C:/tools/claude.exe"
MESSAGES = [
    Message("1", Role.USER, "continue", hidden=True),
    Message("2", Role.ASSISTANT, "The answer", model="m"),
]


def test_the_settings_are_put_to_work_at_the_start(
    wx_app: wx.App, monkeypatch: pytest.MonkeyPatch
) -> None:
    outputs: list[str] = []

    def record(_feedback: Feedback, output_id: str) -> None:
        outputs.append(output_id)

    monkeypatch.setattr(Feedback, "apply_screen_reader_output", record)
    settings = _settings()
    settings.claude_auto_search = False
    settings.claude_path = CLAUDE
    settings.hide_system_messages = False
    window = MainWindow(settings, _runner())
    try:
        assert outputs == [settings.screen_reader_output]
        assert window._run.claude_path == CLAUDE
        window._conversation.set_messages(MESSAGES)
        assert "continue" in window._conversation.GetValue()
        assert window._prompt_area.send_label == "&Send (Ctrl+Enter)"  # the shortcuts are shown
    finally:
        window.Destroy()
        wx.SafeYield()


def test_the_preferences_put_the_same_settings_to_work_when_they_are_validated(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    window._conversation.set_messages(MESSAGES)
    assert "continue" not in window._conversation.GetValue()
    outputs: list[str] = []
    shortcuts: list[str] = []
    monkeypatch.setattr(window._feedback, "apply_screen_reader_output", outputs.append)
    monkeypatch.setattr(window._menu, "apply_shortcuts", lambda _for: shortcuts.append("menu"))
    monkeypatch.setattr(window._prompt_area, "apply_shortcuts", lambda: shortcuts.append("send"))

    def modal(dialog: wx.Dialog) -> int:
        dialog.claude.auto_search.SetValue(False)
        dialog.claude.path.SetValue(CLAUDE)
        dialog.workspace.hide_system_messages.SetValue(False)
        return int(wx.ID_OK)

    monkeypatch.setattr(window._feedback, "modal", modal)
    window._open_preferences(claude_page=False)
    assert outputs == [window._settings.screen_reader_output]
    assert shortcuts == ["menu", "send"]
    assert window._run.claude_path == CLAUDE
    assert "continue" in window._conversation.GetValue()


def test_cancelled_preferences_put_nothing_to_work(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    window._conversation.set_messages(MESSAGES)
    outputs: list[str] = []
    monkeypatch.setattr(window._feedback, "apply_screen_reader_output", outputs.append)

    def modal(dialog: wx.Dialog) -> int:
        dialog.claude.auto_search.SetValue(False)
        dialog.claude.path.SetValue(CLAUDE)
        return int(wx.ID_CANCEL)

    monkeypatch.setattr(window._feedback, "modal", modal)
    window._open_preferences(claude_page=False)
    assert outputs == []
    assert window._run.claude_path == ""
