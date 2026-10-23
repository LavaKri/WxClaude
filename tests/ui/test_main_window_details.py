"""Tests of the main window: details of the messages (context menu actions), usage, task list and
plans."""

import json
from pathlib import Path

import pytest
import wx
from main_window_support import (
    _send,
    _session,
)

from wxclaude.core.conversation.details import DetailAction
from wxclaude.core.conversation.messages import Message, Role
from wxclaude.core.speech.announcements import RecordingMessageSink
from wxclaude.ui import desktop
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

    monkeypatch.setattr(window._feedback, "modal", modal)
    return states


def test_the_usage_item_is_available_without_a_workspace(window: MainWindow) -> None:
    labels = [item.GetItemLabel() for _command, item, _text in window._menu.command_items]
    assert "Claude &usage…\tCtrl+Shift+U" in labels


def test_the_usage_report_says_nothing_is_known_before_the_first_answer(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    states = _capture_dialogs(window, monkeypatch)
    window._actions.show_usage()
    assert states[0]["report"].startswith("No subscription usage information yet")  # type: ignore[attr-defined]


def test_an_answer_feeds_the_usage_report(
    conversation: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    _send(conversation, "hello")
    states = _capture_dialogs(conversation, monkeypatch)
    conversation._actions.show_usage()
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
    conversation._conversations.start_new("Other")
    states = _capture_dialogs(conversation, monkeypatch)
    conversation._actions.show_usage()
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
    conversation._actions.act(DetailAction.TOOLS, answer, -1)
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
    monkeypatch.setattr(desktop, "set_clipboard", lambda text: copied.append(text) or True)
    sink = RecordingMessageSink()
    conversation._feedback.announcements.message_sink = sink
    conversation._actions.act(DetailAction.COPY_MESSAGE, TABLE_AND_LINKS, -1)
    assert copied == [TABLE_AND_LINKS.text]
    assert sink.messages == []  # the user asked for it: nothing to confirm


def test_copying_the_exchange_puts_the_prompt_and_its_answers_on_the_clipboard(
    conversation: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    _send(conversation, "first")
    _send(conversation, "second")
    copied: list[str] = []
    monkeypatch.setattr(desktop, "set_clipboard", lambda text: copied.append(text) or True)
    answer = conversation._conversation.document.spans[-1].message  # the answer to "second"
    conversation._actions.act(DetailAction.COPY_EXCHANGE, answer, -1)
    (text,) = copied
    assert text.startswith("# You say: second\nsecond\n\n## Answer from")
    assert text.endswith("Echo: second")
    assert "first" not in text


def test_the_table_can_be_copied_as_markdown(
    conversation: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    states = _capture_dialogs(conversation, monkeypatch, result=wx.ID_COPY)
    copied: list[str] = []
    monkeypatch.setattr(desktop, "set_clipboard", lambda text: copied.append(text) or True)
    conversation._actions.act(DetailAction.TABLE, TABLE_AND_LINKS, 2)
    assert states[0]["lines"] == ["Name: a.txt, Size: 3"]
    assert copied == ["| Name | Size |\n|---|---|\n| a.txt | 3 |"]


def test_a_link_is_opened_in_the_browser(
    conversation: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    states = _capture_dialogs(conversation, monkeypatch, result=wx.ID_OPEN)
    opened: list[str] = []
    monkeypatch.setattr(desktop, "launch_url", lambda url: opened.append(url) or True)
    conversation._actions.act(DetailAction.LINKS, TABLE_AND_LINKS, 5)
    assert states[0]["lines"] == ["one, https://1.test", "two, ftp://x.test/f"]
    assert opened == ["https://1.test"]


def test_a_link_address_can_be_copied(
    conversation: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    _capture_dialogs(conversation, monkeypatch, result=wx.ID_COPY)
    copied: list[str] = []
    monkeypatch.setattr(desktop, "set_clipboard", lambda text: copied.append(text) or True)
    conversation._actions.act(DetailAction.LINKS, TABLE_AND_LINKS, 5)
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
    conversation._actions.show_tasks()
    assert states[0]["lines"] == ["1, Write, in progress"]


def _plan_item(window: MainWindow) -> wx.MenuItem:
    return next(item for item in window._menu.needs_conversation if item.GetItemLabel() == "Pla&n…")


def test_the_plan_item_is_greyed_without_a_conversation(window: MainWindow) -> None:
    assert not _plan_item(window).IsEnabled()


def test_the_plan_item_is_available_with_a_conversation(conversation: MainWindow) -> None:
    assert _plan_item(conversation).IsEnabled()


def test_the_plan_dialog_lists_the_plans_of_the_conversation_and_selects_the_last(
    conversation: MainWindow, claude_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan_file = claude_config / "plans" / "calm-fox.md"
    plan_file.parent.mkdir(parents=True)
    plan_file.write_text("# The plan", encoding="utf-8")
    other = claude_config / "plans" / "later.md"
    other.write_text("# Later", encoding="utf-8")
    _session(
        claude_config, conversation._workspaces.workspace, identifier=conversation.conversation_id
    )
    session_file = next((claude_config / "projects" / "folder").glob("*.jsonl"))
    entries = [json.loads(line) for line in session_file.read_text(encoding="utf-8").splitlines()]
    for index, path in enumerate((plan_file, other)):
        entries[1]["message"]["content"].append(
            {
                "type": "tool_use",
                "id": f"t{index}",
                "name": "Write",
                "input": {"file_path": str(path), "content": "x"},
            }
        )
    session_file.write_text("\n".join(json.dumps(entry) for entry in entries), encoding="utf-8")
    states = _capture_dialogs(conversation, monkeypatch)
    conversation._actions.show_plans()
    assert states[0]["lines"] == ["calm-fox.md", "later.md"]
    assert states[0]["selection"] == 1


def test_the_plan_dialog_of_a_conversation_without_plan_says_so(
    conversation: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    states = _capture_dialogs(conversation, monkeypatch)
    conversation._actions.show_plans()
    assert states[0]["lines"] == ["No plan in this conversation yet."]


def test_the_task_list_of_a_conversation_without_tasks_says_so(
    conversation: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    states = _capture_dialogs(conversation, monkeypatch)
    conversation._actions.show_tasks()
    assert states[0]["lines"] == ["No task in this conversation yet."]
