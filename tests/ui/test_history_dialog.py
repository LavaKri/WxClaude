"""The history of the announcements in the window: the Help menu item, the dialog, what the box
messages and the changes of workspace and conversation add to it."""

import re
from collections.abc import Callable
from pathlib import Path

import pytest
import wx

from wxclaude.core.speech.announcements import PROGRESS, SECURITY, Announce, Destination
from wxclaude.ui.history_dialog import show_history
from wxclaude.ui.main_window import MainWindow
from wxclaude.ui.text_dialog import TextDialog

pytestmark = pytest.mark.ui

TIME = re.compile(r"\d\d:\d\d ")


def _no_box(window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> list[TextDialog]:
    """Replace the modal display: a text dialog shown is kept (alive) in the returned list."""
    shown: list[TextDialog] = []

    def modal(dialog: wx.Dialog) -> int:
        if isinstance(dialog, TextDialog):
            shown.append(dialog)
        return int(wx.ID_CLOSE)

    monkeypatch.setattr(window._feedback, "modal", modal)
    return shown


def _lines(window: MainWindow) -> list[str]:
    return window._feedback.announcements.history.lines()


def test_the_help_menu_has_the_item_with_no_shortcut_and_it_needs_no_workspace(
    window: MainWindow,
) -> None:
    help_menu = window.GetMenuBar().GetMenu(3)
    items = {item.GetItemLabel(): item for item in help_menu.GetMenuItems()}
    assert "A&nnouncement history…" in items  # no "\t": no shortcut
    assert items["A&nnouncement history…"].IsEnabled()


def test_the_dialog_shows_the_history_with_the_caret_on_the_last_line(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    shown = _no_box(window, monkeypatch)
    window._feedback.say(Announce.CLAUDE_THINKING, name="Claude")
    window._feedback.say(Announce.CLAUDE_DONE, name="Claude")
    show_history(window, window._feedback)
    (dialog,) = shown
    lines = dialog.text.splitlines()
    assert lines[-2].endswith("Claude is thinking.")
    assert lines[-1].endswith("Claude has answered.")
    assert all(TIME.match(line) for line in lines)
    assert dialog._text.GetInsertionPoint() == dialog._text.GetLastPosition()


def test_the_caret_is_still_on_the_last_line_once_the_dialog_is_shown(
    wx_app: wx.App, destroy_after: Callable[[TextDialog], TextDialog]
) -> None:
    """Showing a dialog gives the focus to its field, and Windows selects the whole text of an
    edit control then: the caret must be put back on the last line after that."""
    lines = [f"10:{number:02d} Line {number}" for number in range(40)]
    dialog = destroy_after(TextDialog(None, "History", "&Announcements", lines, caret_at_end=True))
    field = dialog._text
    seen: list[tuple[tuple[int, int], int, int]] = []

    def probe() -> None:  # runs while the dialog is open (ShowModal does not return before)
        seen.append((field.GetSelection(), field.GetInsertionPoint(), field.GetLastPosition()))
        dialog.EndModal(wx.ID_CLOSE)

    wx.CallLater(300, probe)
    dialog.ShowModal()
    (selection, caret, end) = seen[0]
    assert selection == (end, end)
    assert caret == end


def test_an_empty_history_says_so(window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    shown = _no_box(window, monkeypatch)
    show_history(window, window._feedback)
    assert shown[0].text == "No announcement yet."


def test_an_announcement_is_kept_even_when_the_preference_says_no_output(
    window: MainWindow,
) -> None:
    window._settings.set_destination(PROGRESS, Destination.NONE)
    window._feedback.say(Announce.CLAUDE_THINKING, name="Claude")
    assert _lines(window)[-1].endswith("Claude is thinking.")


def test_what_a_message_box_says_is_kept_once_the_box_is_closed(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    _no_box(window, monkeypatch)
    window._feedback.show_error("Claude could not answer.\nThe server refused the key.")
    assert _lines(window)[-1].endswith("Claude could not answer. The server refused the key.")


def test_an_announcement_shown_in_a_box_is_kept_once_not_twice(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    _no_box(window, monkeypatch)
    window._settings.set_destination(SECURITY, Destination.DIALOG)
    window._feedback.say(Announce.FOLDER_RESTRICTED)
    assert [line[6:] for line in _lines(window)] == ["Folder not trusted: restricted mode."]


def test_a_workspace_and_a_conversation_are_marked_after_a_blank_line(
    window: MainWindow, tmp_path: Path
) -> None:
    window.open_workspace(tmp_path)
    window._conversations.start_new("Notes")
    lines = _lines(window)
    assert lines[0].endswith(f"Workspace: {tmp_path.name}")
    assert "" in lines
    assert lines[lines.index("") + 1].endswith("Conversation: Notes")


def test_the_history_is_not_cleared_by_a_change_of_conversation(
    window: MainWindow, tmp_path: Path
) -> None:
    window.open_workspace(tmp_path)
    window._conversations.start_new("One")
    window._feedback.say(Announce.CLAUDE_DONE, name="Claude")
    window._conversations.start_new("Two")
    text = "\n".join(_lines(window))
    assert "Conversation: One" in text
    assert "Claude has answered." in text
    assert _lines(window)[-1].endswith("Conversation: Two")
