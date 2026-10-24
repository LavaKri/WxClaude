"""Tests of the main window: a branch of a conversation and deleting a conversation."""

import json
import shutil
from pathlib import Path

import pytest
import wx
from main_window_support import _send, _session, _use_log

from wxclaude.core.claude.session_reader import read_session
from wxclaude.core.conversation.messages import Role
from wxclaude.core.speech.announcements import RecordingMessageSink
from wxclaude.ui import desktop
from wxclaude.ui.main_window import MainWindow

pytestmark = pytest.mark.ui


def _prompts(path: Path) -> list[str]:
    return [m.text for m in read_session(path).messages if m.role is Role.USER]


def test_a_branch_copies_the_conversation_with_its_first_message(
    conversation: MainWindow, claude_config: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = _use_log(monkeypatch, tmp_path)
    _send(conversation, "first")
    parent = conversation.conversation_id
    screen = conversation._conversations._view
    monkeypatch.setattr(screen, "ask_name", lambda _title, proposal: proposal)
    conversation._conversations.new_branch()
    branch = conversation.conversation_id
    assert branch != parent
    assert conversation.GetTitle().startswith("Notes branch 1 - ")
    assert "Echo: first" in conversation._conversation.GetValue()  # the text stays
    _send(conversation, "second")
    arguments = json.loads(log.read_text(encoding="utf-8"))["arguments"]
    fork = arguments.index("--fork-session")
    assert arguments[fork - 2 : fork + 3] == [
        "--resume",
        parent,
        "--fork-session",
        "--session-id",
        branch,
    ]
    folder = claude_config / "projects" / "fake"
    assert _prompts(folder / f"{branch}.jsonl") == ["first", "second"]
    assert _prompts(folder / f"{parent}.jsonl") == ["first"]  # the original is left as it is
    assert read_session(folder / f"{branch}.jsonl").title == "Notes branch 1"
    # The CLI reports the total of the session, which starts from the one of the original: the
    # message costs 0.001 and not 0.002.
    assert conversation._usage.last_cost == pytest.approx(0.001)
    assert conversation._usage.conversation_cost == pytest.approx(0.001)
    assert read_session(folder / f"{parent}.jsonl").title == "Notes"
    _send(conversation, "third")
    arguments = json.loads(log.read_text(encoding="utf-8"))["arguments"]
    assert arguments[-2:] == ["--resume", branch]  # the branch exists: it is resumed


def _delete_item(window: MainWindow) -> wx.MenuItem:
    return next(
        item
        for item in window._menu.needs_conversation
        if item.GetItemLabel() == "&Delete the conversation"
    )


def test_the_delete_item_needs_a_conversation(window: MainWindow, tmp_path: Path) -> None:
    window.open_workspace(tmp_path)
    assert not _delete_item(window).IsEnabled()
    window._conversations.start_new("Notes")
    assert _delete_item(window).IsEnabled()


def test_a_deleted_conversation_stays_in_the_statistics_of_the_workspace(
    conversation: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    _send(conversation, "hello")
    monkeypatch.setattr(conversation._feedback, "confirm", lambda _title, _message: True)

    def recycle(paths: list[Path]) -> bool:
        for path in paths:
            path.unlink()
        return True

    monkeypatch.setattr(desktop, "move_to_recycle_bin", recycle)
    conversation._conversations.delete()
    assert conversation.conversation_id == ""  # the conversation is gone, its figures stay
    stats = conversation._workspaces.stats
    assert stats is not None
    assert "1 message, in 1 conversation" in stats.lines()


def test_deleting_moves_the_conversation_to_the_recycle_bin_and_opens_the_next(
    conversation: MainWindow, claude_config: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    older = _session(claude_config, tmp_path, age=100, title="Older")
    _send(conversation, "hello")
    deleted = conversation.conversation_id
    tasks = claude_config / "tasks" / deleted
    tasks.mkdir(parents=True)
    asked: list[str] = []

    def confirm(_title: str, message: str) -> bool:
        asked.append(message)
        return True

    monkeypatch.setattr(conversation._feedback, "confirm", confirm)
    moved: list[Path] = []

    def recycle(paths: list[Path]) -> bool:
        for path in paths:
            moved.append(path)
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        return True

    monkeypatch.setattr(desktop, "move_to_recycle_bin", recycle)
    sink = RecordingMessageSink()
    conversation._feedback.announcements.message_sink = sink
    conversation._conversations.delete()
    assert asked == ['Move the conversation "Notes" to the Recycle Bin?']
    assert moved == [claude_config / "projects" / "fake" / f"{deleted}.jsonl", tasks]
    assert 'Conversation "Notes" moved to the Recycle Bin.' in sink.messages
    assert conversation.conversation_id == older
    assert conversation.GetTitle().startswith("Older - ")
    assert conversation._conversation.HasFocus()
