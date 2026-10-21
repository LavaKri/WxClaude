"""Tests of the main window: details of the messages (context menu actions), usage and task list."""

import json
from pathlib import Path

import pytest
import wx
from main_window_support import (
    _Errors,
    _send,
)

from wxclaude.core.announcements import RecordingMessageSink
from wxclaude.core.details import DetailAction
from wxclaude.core.messages import Message, Role
from wxclaude.ui.main_window import MainWindow

pytestmark = pytest.mark.ui


def _capture_dialogs(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch, result: int = wx.ID_CLOSE
) -> list[dict[str, object]]:
    """Replace the modal display: the dialogs shown are kept (alive) in the returned list."""
    shown: list[wx.Dialog] = []
    states: list[dict[str, object]] = []

    def modal(dialog: wx.Dialog) -> int:
        shown.append(dialog)
        states.append(
            {
                "lines": list(dialog._list.GetStrings()) if hasattr(dialog, "_list") else [],
                "report": dialog.report if hasattr(dialog, "report") else "",
                "selection": getattr(dialog, "selection", -1),
            }
        )
        return result

    monkeypatch.setattr(window, "_modal", modal)
    return states


def test_the_usage_item_is_available_without_a_workspace(window: MainWindow) -> None:
    labels = [item.GetItemLabel() for _command, item, _text in window._command_items]
    assert "Claude &usage…\tCtrl+Shift+U" in labels


def test_the_usage_report_says_nothing_is_known_before_the_first_answer(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    states = _capture_dialogs(window, monkeypatch)
    window._on_usage(wx.CommandEvent())
    assert states[0]["report"].startswith("No subscription usage information yet")  # type: ignore[attr-defined]


def test_an_answer_feeds_the_usage_report(
    conversation: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    _send(conversation, "hello")
    states = _capture_dialogs(conversation, monkeypatch)
    conversation._on_usage(wx.CommandEvent())
    report = str(states[0]["report"]).splitlines()
    assert report[0].startswith("5-hour window, 50 % used")
    tokens = "3 in, 4 out, 0 read from the cache, 0 written to the cache"
    assert f"Last message, tokens: {tokens}." in report
    conversation_line = "Conversation since it was opened here: cost 0.0010"
    assert any(line.startswith(conversation_line) for line in report)


def test_another_conversation_starts_the_spending_again(
    conversation: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    _send(conversation, "hello")
    conversation._start_new_conversation("Other")
    states = _capture_dialogs(conversation, monkeypatch)
    conversation._on_usage(wx.CommandEvent())
    report = str(states[0]["report"])
    assert "5-hour window" in report  # the gauges belong to the account
    assert "No message sent yet" in report


def test_the_answer_shown_live_gets_its_tools_from_the_session_file(
    conversation: MainWindow,
) -> None:
    _send(conversation, "hello")
    answer = conversation._conversation.document.spans[-1].message
    assert [tool.name for tool in answer.tools] == ["Read"]
    assert answer.tools[0].result == "x"


def test_the_tools_item_shows_the_tools_of_the_message(
    conversation: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    _send(conversation, "hello")
    answer = conversation._conversation.document.spans[-1].message
    states = _capture_dialogs(conversation, monkeypatch)
    conversation._on_message_action(DetailAction.TOOLS, answer, -1)
    assert states[0]["lines"] == ["Read, n.txt"]


TABLE_AND_LINKS = Message(
    "m",
    Role.ASSISTANT,
    "| Name | Size |\n|---|---|\n| a.txt | 3 |\n\n[one](https://1.test) and [two](ftp://x.test/f)",
    model="m",
)


def test_copying_a_message_puts_its_text_on_the_clipboard(
    conversation: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    copied: list[str] = []
    monkeypatch.setattr(conversation, "_set_clipboard", lambda text: copied.append(text) or True)
    sink = RecordingMessageSink()
    conversation._announcements.message_sink = sink
    conversation._on_message_action(DetailAction.COPY_MESSAGE, TABLE_AND_LINKS, -1)
    assert copied == [TABLE_AND_LINKS.text]
    assert sink.messages[-1] == "Message copied to the clipboard."


def test_a_clipboard_that_cannot_be_used_is_reported(
    conversation: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(conversation, "_set_clipboard", lambda _text: False)
    errors = _Errors(conversation)
    conversation._on_message_action(DetailAction.COPY_MESSAGE, TABLE_AND_LINKS, -1)
    assert errors.messages == ["The clipboard cannot be used."]


def test_the_table_can_be_copied_as_markdown(
    conversation: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    states = _capture_dialogs(conversation, monkeypatch, result=wx.ID_COPY)
    copied: list[str] = []
    monkeypatch.setattr(conversation, "_set_clipboard", lambda text: copied.append(text) or True)
    conversation._on_message_action(DetailAction.TABLE, TABLE_AND_LINKS, 2)
    assert states[0]["lines"] == ["Name: a.txt, Size: 3"]
    assert copied == ["| Name | Size |\n|---|---|\n| a.txt | 3 |"]


def test_a_link_is_opened_in_the_browser(
    conversation: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    states = _capture_dialogs(conversation, monkeypatch, result=wx.ID_OPEN)
    opened: list[str] = []
    monkeypatch.setattr(conversation, "_launch_url", lambda url: opened.append(url) or True)
    conversation._on_message_action(DetailAction.LINKS, TABLE_AND_LINKS, 5)
    assert states[0]["lines"] == ["one, https://1.test", "two, ftp://x.test/f"]
    assert opened == ["https://1.test"]


def test_a_link_of_another_kind_is_never_handed_to_the_system(
    conversation: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    def modal(dialog: wx.Dialog) -> int:
        dialog._list.SetSelection(1)  # the file: link
        return wx.ID_OPEN

    monkeypatch.setattr(conversation, "_modal", modal)
    opened: list[str] = []
    monkeypatch.setattr(conversation, "_launch_url", lambda url: opened.append(url) or True)
    errors = _Errors(conversation)
    conversation._on_message_action(DetailAction.LINKS, TABLE_AND_LINKS, 5)
    assert opened == []
    assert errors.messages == ["This kind of address is not opened from here: ftp://x.test/f"]


def test_a_browser_that_refuses_is_reported(
    conversation: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    _capture_dialogs(conversation, monkeypatch, result=wx.ID_OPEN)
    monkeypatch.setattr(conversation, "_launch_url", lambda _url: False)
    errors = _Errors(conversation)
    conversation._on_message_action(DetailAction.LINKS, TABLE_AND_LINKS, 5)
    assert errors.messages == ["The address https://1.test cannot be opened."]


def test_a_link_address_can_be_copied(
    conversation: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    _capture_dialogs(conversation, monkeypatch, result=wx.ID_COPY)
    copied: list[str] = []
    monkeypatch.setattr(conversation, "_set_clipboard", lambda text: copied.append(text) or True)
    conversation._on_message_action(DetailAction.LINKS, TABLE_AND_LINKS, 5)
    assert copied == ["https://1.test"]


def test_the_task_list_reads_the_tasks_of_the_conversation(
    conversation: MainWindow, claude_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = claude_config / "tasks" / conversation.conversation_id
    folder.mkdir(parents=True)
    (folder / "1.json").write_text(
        json.dumps({"id": "1", "subject": "Write", "status": "in_progress"}), encoding="utf-8"
    )
    states = _capture_dialogs(conversation, monkeypatch)
    conversation._on_tasks(wx.CommandEvent())
    assert states[0]["lines"] == ["1, Write, in progress"]


def test_the_task_list_of_a_conversation_without_tasks_says_so(
    conversation: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    states = _capture_dialogs(conversation, monkeypatch)
    conversation._on_tasks(wx.CommandEvent())
    assert states[0]["lines"] == ["No task in this conversation yet."]
