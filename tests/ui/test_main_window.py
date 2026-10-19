import json
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import wx

from wxclaude.core.agents import Agent
from wxclaude.core.announcements import RecordingMessageSink
from wxclaude.core.conversations import is_conversation_id, new_conversation_id
from wxclaude.core.messages import Message, Role
from wxclaude.core.runner import ClaudeRunner
from wxclaude.core.search import SearchOptions
from wxclaude.core.settings import Settings
from wxclaude.core.workspace_state import WorkspaceState
from wxclaude.ui.main_window import MainWindow
from wxclaude.ui.message_sinks import create_sink

pytestmark = pytest.mark.ui

FAKE = Path(__file__).resolve().parent.parent / "fakes" / "fake_claude.py"
OPUS = Agent(model="opus", effort="high", permission_mode="manual")


def _settings(store: Path | None = None) -> Settings:
    settings = Settings.load(store)
    settings.default_agent = OPUS
    settings.screen_reader_output = "none"  # UI Automation is tested on its own below
    return settings


def _runner() -> ClaudeRunner:
    return ClaudeRunner([sys.executable, str(FAKE)])


@pytest.fixture
def window(wx_app: wx.App):
    window = MainWindow(_settings(), _runner())
    yield window
    window.Destroy()
    wx.SafeYield()


@pytest.fixture
def conversation(window: MainWindow, tmp_path: Path) -> MainWindow:
    """A window with a workspace and a conversation, as after "New conversation"."""
    window.open_workspace(tmp_path)
    window._start_new_conversation("Notes")
    return window


def _enabled(items: list[wx.MenuItem]) -> list[bool]:
    return [item.IsEnabled() for item in items]


def test_at_the_first_start_there_is_no_workspace_and_no_conversation(window: MainWindow) -> None:
    assert window.GetTitle() == "WxClaude"
    assert window.conversation_id == ""
    assert not window.can_send
    assert not window._prompt.IsEnabled()
    assert not any(_enabled(window._needs_workspace))
    assert not any(_enabled(window._needs_conversation))
    assert not window._interrupt_item.IsEnabled()
    assert not window._recent_item.IsEnabled()  # nothing opened yet


def test_a_workspace_without_conversation_only_allows_to_start_one(
    window: MainWindow, tmp_path: Path
) -> None:
    window.open_workspace(tmp_path)
    assert window.GetTitle() == f"{tmp_path.name} - WxClaude"
    assert all(_enabled(window._needs_workspace))
    assert not any(_enabled(window._needs_conversation))
    assert not window.can_send


def test_a_conversation_enables_everything_that_needs_one(conversation: MainWindow) -> None:
    assert all(_enabled(conversation._needs_workspace))
    assert all(_enabled(conversation._needs_conversation))
    assert conversation._prompt.IsEnabled()
    assert conversation.can_send
    assert is_conversation_id(conversation.conversation_id)
    state = conversation._state
    assert state is not None
    assert state.current_conversation == conversation.conversation_id
    assert state.conversations[conversation.conversation_id].name == "Notes"
    assert state.conversations[conversation.conversation_id].agent == OPUS


def test_another_workspace_closes_the_conversation(
    conversation: MainWindow, tmp_path: Path
) -> None:
    other = tmp_path / "other"
    other.mkdir()
    conversation.open_workspace(other)
    assert conversation.conversation_id == ""
    assert not any(_enabled(conversation._needs_conversation))
    assert not conversation._prompt.IsEnabled()


def test_the_same_workspace_keeps_the_conversation(
    conversation: MainWindow, tmp_path: Path
) -> None:
    identifier = conversation.conversation_id
    conversation.open_workspace(tmp_path)
    assert conversation.conversation_id == identifier


def _session(
    claude_config: Path,
    workspace: Path,
    age: int = 0,
    prompt: str = "Hello",
    title: str = "",
    identifier: str = "",
    effort: str = "",
) -> str:
    """Write a session file of ``workspace``; ``age`` seconds old; return its identifier."""
    identifier = identifier or new_conversation_id()
    folder = claude_config / "projects" / "folder"
    folder.mkdir(parents=True, exist_ok=True)
    when = datetime.now(UTC) - timedelta(seconds=age)
    entries: list[dict[str, object]] = [
        {
            "type": "user",
            "cwd": str(workspace),
            "permissionMode": "plan",
            "uuid": "u",
            "timestamp": when.isoformat(),
            "message": {"role": "user", "content": prompt},
        },
        {
            "type": "assistant",
            "uuid": "a",
            "effort": effort or "low",
            "timestamp": when.isoformat(),
            "message": {
                "role": "assistant",
                "model": "claude-haiku-4-5",
                "content": [{"type": "text", "text": "Hi"}],
            },
        },
    ]
    if title:
        entries.append({"type": "custom-title", "customTitle": title})
    (folder / f"{identifier}.jsonl").write_text(
        "\n".join(json.dumps(entry) for entry in entries), encoding="utf-8"
    )
    return identifier


def test_the_remembered_conversation_of_the_last_workspace_is_selected(
    wx_app: wx.App, tmp_path: Path, claude_config: Path
) -> None:
    older = _session(claude_config, tmp_path, age=100, title="Older")
    _session(claude_config, tmp_path, age=0, title="Newer")
    settings = _settings(tmp_path / "config" / "settings.json")
    settings.last_workspace = str(tmp_path)
    state = WorkspaceState.load(tmp_path, settings.workspaces_dir)
    state.remember(older, "Mine", Agent(model="opus"))
    state.save()
    reopened = MainWindow(settings)
    assert reopened.GetTitle() == f"Mine - {tmp_path.name} - WxClaude"
    assert reopened.conversation_id == older
    assert reopened._agent == Agent(model="opus", effort="high", permission_mode="manual")
    assert reopened.can_send
    assert "# You say: Hello" in reopened._conversation.GetValue()
    reopened.Destroy()
    wx.SafeYield()


def test_an_unknown_session_takes_the_agent_of_its_last_message(
    wx_app: wx.App, tmp_path: Path, claude_config: Path
) -> None:
    identifier = _session(claude_config, tmp_path, effort="max")
    settings = _settings(tmp_path / "config" / "settings.json")
    settings.last_workspace = str(tmp_path)
    window = MainWindow(settings)
    expected = Agent(model="claude-haiku-4-5", effort="max", permission_mode="plan")
    assert window.conversation_id == identifier
    assert window._agent == expected
    window.Destroy()
    wx.SafeYield()
    # It is now remembered: another start finds the same agent in the workspace file.
    again = MainWindow(settings)
    assert again._agent == expected
    state = WorkspaceState.load(tmp_path, settings.workspaces_dir)
    assert state.conversations[identifier].agent == expected
    again.Destroy()
    wx.SafeYield()


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
    assert conversation._state is not None
    assert conversation._state.current_conversation == newest


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
    window._agent = Agent(model="haiku")
    window._on_refresh_conversation(wx.CommandEvent())
    assert len(view.document.spans) == 3
    assert "Added elsewhere" in view.GetValue()
    assert window._agent == Agent(model="haiku")  # the agent comes from the memory, not the file


def test_refreshing_a_conversation_without_history_says_so(conversation: MainWindow) -> None:
    sink = RecordingMessageSink()
    conversation._announcements.message_sink = sink
    conversation._on_refresh_conversation(wx.CommandEvent())
    assert sink.messages == ["This conversation has no history yet."]


def test_a_workspace_without_conversation_gets_none(
    conversation: MainWindow, tmp_path: Path
) -> None:
    (tmp_path / "empty").mkdir()
    conversation.open_workspace(tmp_path / "empty")
    assert conversation.conversation_id == ""
    assert conversation._conversation.GetValue() == ""
    assert not conversation.can_send


def test_without_the_option_nothing_is_opened(wx_app: wx.App, tmp_path: Path) -> None:
    settings = _settings()
    settings.reopen_last = False
    settings.last_workspace = str(tmp_path)
    fresh = MainWindow(settings)
    assert fresh.GetTitle() == "WxClaude"
    assert fresh.conversation_id == ""
    fresh.Destroy()
    wx.SafeYield()


def test_a_workspace_that_no_longer_exists_is_not_opened(wx_app: wx.App, tmp_path: Path) -> None:
    settings = _settings()
    settings.last_workspace = str(tmp_path / "gone")
    fresh = MainWindow(settings)
    assert fresh.GetTitle() == "WxClaude"
    assert fresh.conversation_id == ""
    assert not any(_enabled(fresh._needs_workspace))
    fresh.Destroy()
    wx.SafeYield()


def test_the_send_buttons_show_their_shortcuts(window: MainWindow) -> None:
    assert window._send_button.GetLabel() == "&Send (Ctrl+Enter)"
    assert window._alternative_button.GetLabel().endswith("(Shift+Enter)")


def test_alternative_agent_overrides_only_what_it_sets(window: MainWindow) -> None:
    assert window.agent_for(alternative=False) == OPUS
    assert window.agent_for(alternative=True) == Agent(
        model="opus", effort="low", permission_mode="manual"
    )


@pytest.mark.skipif(sys.platform != "win32", reason="UI Automation exists only on Windows")
def test_a_ui_automation_notification_can_be_raised(window: MainWindow) -> None:
    sink = create_sink("uia", window)
    sink.show("hello")
    sink.close()


def _wait_until_idle(window: MainWindow, timeout: float = 30) -> None:
    """Let the events of the runner reach the window until Claude is done."""
    deadline = time.monotonic() + timeout
    while window._busy:
        assert time.monotonic() < deadline, "Claude did not finish"
        wx.Yield()
        time.sleep(0.02)
    wx.Yield()


class _Errors:
    def __init__(self, window: MainWindow) -> None:
        self.messages: list[str] = []
        window._show_error = self.messages.append  # type: ignore[method-assign]


def _use_log(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    log = tmp_path / "fake-log.json"
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    return log


def test_sending_runs_claude_and_shows_the_answer(
    conversation: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = _use_log(monkeypatch, tmp_path)
    sink = RecordingMessageSink()
    conversation._announcements.message_sink = sink
    conversation._prompt.SetValue("hello")
    conversation.send_prompt(alternative=False)
    assert conversation._busy
    assert not conversation.can_send
    assert conversation._prompt.GetValue() == ""
    assert "# You say: hello" in conversation._conversation.GetValue()
    _wait_until_idle(conversation)
    text = conversation._conversation.GetValue()
    assert "## Answer from claude-opus-fake, effort high\nEcho: hello" in text
    assert conversation.can_send
    assert sink.messages[-1] == "Claude has answered."
    assert sink.messages.count("Claude is thinking.") == 1  # not repeated
    assert "Claude uses the tool Read." in sink.messages
    sent = json.loads(log.read_text(encoding="utf-8"))
    assert sent["arguments"][-2:] == ["--session-id", conversation.conversation_id]
    assert sent["prompt"] == "hello"
    assert sent["cwd"].lower() == str(tmp_path).lower()
    # The view now equals the session file written by the CLI.
    assert not text.count("local")


def test_the_second_message_resumes_the_conversation(
    conversation: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = _use_log(monkeypatch, tmp_path)
    for prompt in ("one", "two"):
        conversation._prompt.SetValue(prompt)
        conversation.send_prompt(alternative=False)
        _wait_until_idle(conversation)
    sent = json.loads(log.read_text(encoding="utf-8"))
    assert sent["arguments"][-2:] == ["--resume", conversation.conversation_id]
    text = conversation._conversation.GetValue()
    assert text.index("Echo: one") < text.index("# You say: two") < text.index("Echo: two")


def test_the_alternative_agent_is_used_by_the_alternative_send(
    conversation: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = _use_log(monkeypatch, tmp_path)
    conversation._prompt.SetValue("hello")
    conversation.send_prompt(alternative=True)
    _wait_until_idle(conversation)
    arguments = json.loads(log.read_text(encoding="utf-8"))["arguments"]
    assert arguments[arguments.index("--effort") + 1] == "low"
    assert conversation._agent == OPUS  # the agent of the conversation is not changed


def test_progress_is_only_in_the_status_bar_when_it_is_not_announced(
    conversation: MainWindow,
) -> None:
    conversation._settings.announce_progress = False
    sink = RecordingMessageSink()
    conversation._announcements.message_sink = sink
    conversation._prompt.SetValue("hello")
    conversation.send_prompt(alternative=False)
    _wait_until_idle(conversation)
    assert sink.messages == ["Claude has answered."]  # the end is always said


def test_a_failure_is_announced_and_shown_in_a_dialog(
    conversation: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_CLAUDE", "crash")
    errors = _Errors(conversation)
    sink = RecordingMessageSink()
    conversation._announcements.message_sink = sink
    conversation._prompt.SetValue("hello")
    conversation.send_prompt(alternative=False)
    _wait_until_idle(conversation)
    assert len(errors.messages) == 1
    assert "not logged in" in errors.messages[0]
    assert sink.messages[-1].startswith("Claude could not answer: fake claude: not logged in")
    assert conversation.can_send


def test_a_missing_claude_keeps_the_prompt(
    conversation: MainWindow, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    conversation._runner = ClaudeRunner()
    errors = _Errors(conversation)
    conversation._prompt.SetValue("hello")
    conversation.send_prompt(alternative=False)
    assert len(errors.messages) == 1
    assert conversation._prompt.GetValue() == "hello"
    assert not conversation._busy
    assert conversation._conversation.GetValue() == ""


def test_interrupting_stops_claude(
    conversation: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_CLAUDE", "slow")
    errors = _Errors(conversation)
    sink = RecordingMessageSink()
    conversation._announcements.message_sink = sink
    conversation._prompt.SetValue("hello")
    conversation.send_prompt(alternative=False)
    assert conversation._interrupt_item.IsEnabled()
    conversation._on_interrupt(wx.CommandEvent())
    _wait_until_idle(conversation)
    assert sink.messages[-2:] == ["Interrupting Claude.", "Claude was interrupted."]
    assert errors.messages == []
    assert not conversation._interrupt_item.IsEnabled()


def test_nothing_is_sent_without_a_conversation(window: MainWindow) -> None:
    window._prompt.SetValue("hello")
    window.send_prompt(alternative=False)
    assert window._conversation.GetValue() == ""


def _search_window(conversation: MainWindow) -> tuple[MainWindow, RecordingMessageSink, list[str]]:
    conversation._conversation.set_messages(
        [
            Message("1", Role.USER, "Intro.\none fish\ntwo fish"),
            Message("2", Role.ASSISTANT, "red fish\nblue Fish", model="m"),
        ]
    )
    sink = RecordingMessageSink()
    conversation._announcements.message_sink = sink
    infos: list[str] = []
    conversation._show_info = infos.append  # type: ignore[method-assign]
    return conversation, sink, infos


def test_searching_walks_through_the_occurrences_and_announces_the_line(
    conversation: MainWindow,
) -> None:
    window, sink, infos = _search_window(conversation)
    window._search_options = SearchOptions("fish")
    view = window._conversation
    window.search(backwards=False)
    assert sink.messages[-1] == "one fish"
    assert view.selection_indexes() == (view.text.index("fish"), view.text.index("fish") + 4)
    assert view.HasFocus()
    window.search(backwards=False)
    assert sink.messages[-1] == "two fish"
    window.search(backwards=False)
    assert sink.messages[-1] == "red fish"
    window.search(backwards=False)
    assert sink.messages[-1] == "blue Fish"  # the case is ignored by default
    assert infos == []
    window.search(backwards=False)
    assert infos == ['No next occurrence of "fish".']
    window.search(backwards=True)
    assert sink.messages[-1] == "red fish"
    assert len(infos) == 1


def test_searching_backwards_stops_at_the_first_occurrence(conversation: MainWindow) -> None:
    window, sink, infos = _search_window(conversation)
    window._search_options = SearchOptions("fish", match_case=True)
    view = window._conversation
    view.SetInsertionPoint(len(view.text))
    window.search(backwards=True)
    assert sink.messages[-1] == "red fish"
    window.search(backwards=True)
    window.search(backwards=True)
    assert sink.messages[-1] == "one fish"
    window.search(backwards=True)
    assert infos == ['No previous occurrence of "fish".']


def test_a_term_that_is_not_there_is_reported(conversation: MainWindow) -> None:
    window, sink, infos = _search_window(conversation)
    window._search_options = SearchOptions("zebra")
    window.search(backwards=False)
    assert infos == ['No next occurrence of "zebra".']
    assert sink.messages == []


def test_next_without_a_previous_search_opens_the_dialog(
    conversation: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[bool] = []
    monkeypatch.setattr(conversation, "_on_find", lambda _event: opened.append(True))
    conversation._on_find_next(wx.CommandEvent())
    conversation._on_find_previous(wx.CommandEvent())
    assert opened == [True, True]


def test_the_search_commands_have_the_classic_shortcuts(conversation: MainWindow) -> None:
    labels = [item.GetItemLabel() for item in conversation._needs_conversation]
    assert "&Find…	Ctrl+F" in labels
    assert "Find &next	F3" in labels
    assert "Find &previous	Shift+F3" in labels
