"""Tests of the main window: workspaces and conversations (selection, refresh, folder)."""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
import wx
from main_window_support import (
    OPUS,
    _enabled,
    _Errors,
    _session,
    _settings,
)

from wxclaude.core.config.agents import Agent
from wxclaude.core.config.workspace_state import WorkspaceState
from wxclaude.core.conversation.conversations import is_conversation_id
from wxclaude.core.speech.announcements import RecordingMessageSink
from wxclaude.ui import desktop
from wxclaude.ui.main_window import MainWindow

pytestmark = pytest.mark.ui


def test_at_the_first_start_there_is_no_workspace_and_no_conversation(window: MainWindow) -> None:
    assert window.GetTitle() == "WxClaude"
    assert window.conversation_id == ""
    assert not window.can_send
    assert not window._prompt.IsEnabled()
    assert not any(_enabled(window._menu.needs_workspace))
    assert not any(_enabled(window._menu.needs_conversation))
    assert not window._menu.interrupt_item.IsEnabled()
    assert not window._menu.recent_item.IsEnabled()  # nothing opened yet


def test_a_workspace_without_conversation_only_allows_to_start_one(
    window: MainWindow, tmp_path: Path
) -> None:
    window.open_workspace(tmp_path)
    assert window.GetTitle() == f"{tmp_path.name} - WxClaude"
    assert all(_enabled(window._menu.needs_workspace))
    assert not any(_enabled(window._menu.needs_conversation))
    assert not window.can_send


def test_a_conversation_enables_everything_that_needs_one(conversation: MainWindow) -> None:
    assert all(_enabled(conversation._menu.needs_workspace))
    assert all(_enabled(conversation._menu.needs_conversation))
    assert conversation._prompt.IsEnabled()
    assert conversation.can_send
    assert is_conversation_id(conversation.conversation_id)
    state = conversation._workspaces.state
    assert state is not None
    assert state.current_conversation == conversation.conversation_id
    assert state.conversations[conversation.conversation_id].agent == OPUS


def test_another_workspace_closes_the_conversation(
    conversation: MainWindow, tmp_path: Path
) -> None:
    other = tmp_path / "other"
    other.mkdir()
    conversation.open_workspace(other)
    assert conversation.conversation_id == ""
    assert not any(_enabled(conversation._menu.needs_conversation))
    assert not conversation._prompt.IsEnabled()


def test_the_same_workspace_keeps_the_conversation(
    conversation: MainWindow, tmp_path: Path
) -> None:
    identifier = conversation.conversation_id
    conversation.open_workspace(tmp_path)
    assert conversation.conversation_id == identifier


def test_the_remembered_conversation_of_the_last_workspace_is_selected(
    destroy_after: Callable[[MainWindow], MainWindow], tmp_path: Path, claude_config: Path
) -> None:
    older = _session(claude_config, tmp_path, age=100, title="Older")
    _session(claude_config, tmp_path, age=0, title="Newer")
    settings = _settings(tmp_path / "config" / "settings.json")
    settings.last_workspace = str(tmp_path)
    state = WorkspaceState.load(tmp_path, settings.workspaces_dir)
    state.remember(older, Agent(model="opus"))
    state.save()
    reopened = destroy_after(MainWindow(settings))
    # The name is the one of the session, kept by the CLI.
    assert reopened.GetTitle() == f"Older - {tmp_path.name} - WxClaude"
    assert reopened.conversation_id == older
    expected = Agent(model="opus", effort="high", permission_mode="manual")
    assert reopened._conversations.agent == expected
    assert reopened.can_send
    assert "# You say: Hello" in reopened._conversation.GetValue()


def test_an_unknown_session_takes_the_agent_of_its_last_message(
    destroy_after: Callable[[MainWindow], MainWindow], tmp_path: Path, claude_config: Path
) -> None:
    identifier = _session(claude_config, tmp_path, effort="max")
    settings = _settings(tmp_path / "config" / "settings.json")
    settings.last_workspace = str(tmp_path)
    window = destroy_after(MainWindow(settings))
    expected = Agent(model="claude-haiku-4-5", effort="max", permission_mode="plan")
    assert window.conversation_id == identifier
    assert window._conversations.agent == expected
    window.Destroy()
    wx.SafeYield()
    # It is now remembered: another start finds the same agent in the workspace file.
    again = destroy_after(MainWindow(settings))
    assert again._conversations.agent == expected
    state = WorkspaceState.load(tmp_path, settings.workspaces_dir)
    assert state.conversations[identifier].agent == expected


def test_without_a_remembered_conversation_the_most_recent_one_is_selected(
    conversation: MainWindow, tmp_path: Path, claude_config: Path
) -> None:
    other = tmp_path / "other"
    other.mkdir()
    _session(claude_config, other, age=500)
    newest = _session(claude_config, other, age=10, title="Newest")
    _session(claude_config, other, age=900)
    conversation.open_workspace(other)
    assert conversation.conversation_id == newest
    assert conversation.GetTitle() == "Newest - other - WxClaude"
    assert conversation._workspaces.state is not None
    assert conversation._workspaces.state.current_conversation == newest


def test_refreshing_reads_the_session_file_again(
    window: MainWindow, tmp_path: Path, claude_config: Path
) -> None:
    identifier = _session(claude_config, tmp_path)
    window.open_workspace(tmp_path)
    assert window.conversation_id == identifier
    view = window._conversation
    assert len(view.document.spans) == 2
    session_file = claude_config / "projects" / "folder" / f"{identifier}.jsonl"
    extra = {
        "type": "user",
        "uuid": "u2",
        "timestamp": datetime.now(UTC).isoformat(),
        "message": {"role": "user", "content": "Added elsewhere"},
    }
    with session_file.open("a", encoding="utf-8") as file:
        file.write("\n" + json.dumps(extra))
    window._conversations.agent = Agent(model="haiku")
    window._on_refresh_conversation(wx.CommandEvent())
    assert len(view.document.spans) == 3
    assert "Added elsewhere" in view.GetValue()
    assert window._conversations.agent == Agent(
        model="haiku"
    )  # the agent comes from the memory, not the file


def test_refreshing_a_conversation_without_history_says_so(conversation: MainWindow) -> None:
    sink = RecordingMessageSink()
    conversation._feedback.announcements.message_sink = sink
    conversation._on_refresh_conversation(wx.CommandEvent())
    assert sink.messages == ["This conversation has no history yet."]


def test_without_the_option_nothing_is_opened(
    destroy_after: Callable[[MainWindow], MainWindow], tmp_path: Path
) -> None:
    settings = _settings()
    settings.reopen_last = False
    settings.last_workspace = str(tmp_path)
    fresh = destroy_after(MainWindow(settings))
    assert fresh.GetTitle() == "WxClaude"
    assert fresh.conversation_id == ""


def test_a_workspace_that_no_longer_exists_is_not_opened(
    destroy_after: Callable[[MainWindow], MainWindow], tmp_path: Path
) -> None:
    settings = _settings()
    settings.last_workspace = str(tmp_path / "gone")
    fresh = destroy_after(MainWindow(settings))
    assert fresh.GetTitle() == "WxClaude"
    assert fresh.conversation_id == ""
    assert not any(_enabled(fresh._menu.needs_workspace))


def test_the_help_page_is_opened_in_the_browser(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[Path] = []
    page = tmp_path / "fr.html"
    monkeypatch.setattr("wxclaude.presenters.file_presenter.help_page", lambda language: page)
    monkeypatch.setattr(desktop, "launch_file", lambda path: opened.append(path) or True)
    window._files.show_help("fr")
    assert opened == [page]


def test_the_workspace_folder_is_opened_in_the_file_explorer(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[Path] = []
    monkeypatch.setattr(desktop, "launch_folder", lambda folder: opened.append(folder) or True)
    errors = _Errors(window)
    window.open_workspace(tmp_path)
    window._files.open_folder(window._workspaces.workspace)
    assert opened == [tmp_path]
    assert errors.messages == []


def test_the_folder_item_needs_a_workspace(window: MainWindow, tmp_path: Path) -> None:
    folder_item = next(
        item
        for item in window._menu.needs_workspace
        if item.GetItemLabel() == "Open the workspace &folder"
    )
    assert not folder_item.IsEnabled()
    window.open_workspace(tmp_path)
    assert folder_item.IsEnabled()
