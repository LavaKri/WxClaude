"""Tests of the main window: search in the conversation and where the focus goes."""

from pathlib import Path

import pytest
import wx
from main_window_support import (
    _session,
    _settings,
    _wait_until_idle,
)

from wxclaude.core.conversation.messages import Message, Role
from wxclaude.core.conversation.search import SearchOptions
from wxclaude.core.speech.announcements import SEARCH_FAILED, Destination, RecordingMessageSink
from wxclaude.ui.main_window import MainWindow

pytestmark = pytest.mark.ui


def _search_window(conversation: MainWindow) -> tuple[MainWindow, RecordingMessageSink, list[str]]:
    conversation._conversation.set_messages(
        [
            Message("1", Role.USER, "Intro.\none fish\ntwo fish"),
            Message("2", Role.ASSISTANT, "red fish\nblue Fish", model="m"),
        ]
    )
    sink = RecordingMessageSink()
    conversation._feedback.announcements.message_sink = sink
    infos: list[str] = []
    conversation._feedback.show_info = infos.append  # type: ignore[method-assign]
    return conversation, sink, infos


def test_searching_walks_through_the_occurrences_and_announces_the_line(
    conversation: MainWindow,
) -> None:
    window, sink, infos = _search_window(conversation)
    window._search.options = SearchOptions("fish")
    view = window._conversation
    window._search.search(backwards=False)
    assert sink.messages[-1] == "one fish"
    assert view.selection_indexes() == (view.text.index("fish"), view.text.index("fish") + 4)
    assert view.HasFocus()
    window._search.search(backwards=False)
    assert sink.messages[-1] == "two fish"
    window._search.search(backwards=False)
    assert sink.messages[-1] == "red fish"
    window._search.search(backwards=False)
    assert sink.messages[-1] == "blue Fish"  # the case is ignored by default
    assert infos == []
    window._search.search(backwards=False)
    assert sink.messages[-1] == 'No next occurrence of "fish".'  # a message by default
    assert "No next occurrence" not in window.GetStatusBar().GetStatusText(2)  # not in the bar
    window._search.search(backwards=True)
    assert sink.messages[-1] == "red fish"
    assert infos == []


def test_searching_backwards_stops_at_the_first_occurrence(conversation: MainWindow) -> None:
    window, sink, infos = _search_window(conversation)
    window._search.options = SearchOptions("fish", match_case=True)
    view = window._conversation
    view.SetInsertionPoint(len(view.text))
    window._search.search(backwards=True)
    assert sink.messages[-1] == "red fish"
    window._search.search(backwards=True)
    window._search.search(backwards=True)
    assert sink.messages[-1] == "one fish"
    window._search.search(backwards=True)
    assert sink.messages[-1] == 'No previous occurrence of "fish".'
    assert infos == []


def test_a_term_that_is_not_there_is_reported(conversation: MainWindow) -> None:
    window, sink, infos = _search_window(conversation)
    window._search.options = SearchOptions("zebra")
    window._search.search(backwards=False)
    assert sink.messages == ['No next occurrence of "zebra".']
    assert infos == []


def test_an_unsuccessful_search_can_open_a_dialog_or_say_nothing(conversation: MainWindow) -> None:
    window, sink, infos = _search_window(conversation)
    window._search.options = SearchOptions("zebra")
    window._settings.set_destination(SEARCH_FAILED, Destination.DIALOG)
    window._search.search(backwards=False)
    assert infos == ['No next occurrence of "zebra".']
    assert sink.messages == []
    window._settings.set_destination(SEARCH_FAILED, Destination.NONE)
    window._search.search(backwards=False)
    assert infos == ['No next occurrence of "zebra".']  # nothing more
    assert sink.messages == []


def test_next_without_a_previous_search_opens_the_dialog(
    conversation: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[bool] = []
    monkeypatch.setattr(conversation._search, "find", lambda: opened.append(True))
    conversation._search.find_next()
    conversation._search.find_previous()
    assert opened == [True, True]


def test_the_search_commands_have_the_classic_shortcuts(conversation: MainWindow) -> None:
    labels = [item.GetItemLabel() for item in conversation._menu.needs_conversation]
    assert "&Find…	Ctrl+F" in labels
    assert "Find &next	F3" in labels
    assert "Find &previous	Shift+F3" in labels


def _last_prompt_start(window: MainWindow) -> int:
    view = window._conversation
    return view.text.rindex("# You say:")


def test_a_loaded_conversation_puts_the_focus_on_my_last_message(
    wx_app: wx.App, tmp_path: Path, claude_config: Path
) -> None:
    _session(claude_config, tmp_path, prompt="Last question")
    settings = _settings(tmp_path / "config" / "settings.json")
    settings.last_workspace = str(tmp_path)
    window = MainWindow(settings)  # at startup
    try:
        assert window._conversation.HasFocus()
        assert window._conversation.GetInsertionPoint() == _last_prompt_start(window)
        window._prompt.SetFocus()
        window._conversation.SetInsertionPoint(0)
        window._on_refresh_conversation(wx.CommandEvent())  # F5
        assert window._conversation.HasFocus()
        assert window._conversation.GetInsertionPoint() == _last_prompt_start(window)
    finally:
        window.Destroy()
        wx.SafeYield()


def test_opening_a_workspace_puts_the_focus_on_my_last_message(
    window: MainWindow, tmp_path: Path, claude_config: Path
) -> None:
    other = tmp_path / "other"
    other.mkdir()
    _session(claude_config, other, prompt="Question")
    window._prompt.SetFocus()
    window.open_workspace(other)
    assert window._conversation.HasFocus()
    assert window._conversation.GetInsertionPoint() == _last_prompt_start(window)


def test_sending_puts_the_focus_on_the_prompt_just_sent(conversation: MainWindow) -> None:
    wx.Yield()  # the focus of the startup first
    conversation._prompt.SetFocus()
    conversation._prompt.SetValue("hello")
    conversation.send_prompt(alternative=False)
    view = conversation._conversation
    assert view.HasFocus()
    assert view.GetInsertionPoint() == view.text.rindex("# You say: hello")
    _wait_until_idle(conversation)
    assert view.HasFocus()  # the end of the answer does not move it


def test_a_workspace_without_conversation_focuses_the_view_and_says_so(
    conversation: MainWindow, tmp_path: Path
) -> None:
    sink = RecordingMessageSink()
    conversation._feedback.announcements.message_sink = sink
    empty = tmp_path / "empty-workspace"
    empty.mkdir()
    conversation._prompt.SetFocus()
    conversation.open_workspace(empty)
    assert conversation._conversation.HasFocus()
    assert not conversation._prompt.IsEnabled()
    assert not conversation._send_button.IsEnabled() or not conversation.can_send
    assert sink.messages[-1] == "No conversation in this workspace."


def test_the_focus_comes_back_after_a_dialog(conversation: MainWindow) -> None:
    conversation.Show()  # the focus only exists in a window that is shown
    wx.Yield()
    conversation._prompt.SetFocus()
    wx.CallAfter(lambda: wx.GetTopLevelWindows()[-1].EndModal(wx.ID_CANCEL))
    conversation._search.find()  # opens the Find dialog, closed at once
    wx.Yield()
    assert conversation._prompt.HasFocus()
