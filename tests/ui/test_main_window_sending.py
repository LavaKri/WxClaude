"""Tests of the main window: sending a prompt (buttons, agents, run, failures, status bar)."""

import json
import sys
from pathlib import Path

import pytest
import wx
from main_window_support import (
    OPUS,
    _Errors,
    _send,
    _use_log,
    _wait_until_idle,
)

from wxclaude.core.claude.claude_projects import claude_config_dir
from wxclaude.core.claude.events import ToolUsed, TurnEnded, TurnResult
from wxclaude.core.claude.runner import ClaudeRunner
from wxclaude.core.config.agents import Agent
from wxclaude.core.speech.announcements import (
    END_OF_ANSWER,
    PROGRESS,
    Destination,
    RecordingMessageSink,
    RecordingSoundPlayer,
)
from wxclaude.ui.main_window import MainWindow
from wxclaude.ui.message_sinks import create_sink

pytestmark = pytest.mark.ui


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


def test_sending_runs_claude_and_shows_the_answer(
    conversation: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = _use_log(monkeypatch, tmp_path)
    sink = RecordingMessageSink()
    conversation._feedback.announcements.message_sink = sink
    conversation._settings.set_destination(END_OF_ANSWER, Destination.MESSAGE)
    conversation._prompt.SetValue("hello")
    conversation.send_prompt(alternative=False)
    assert conversation._run.busy
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
    # The first message gives the name of the conversation to the CLI, which keeps it.
    assert sent["arguments"][-4:] == [
        "--session-id",
        conversation.conversation_id,
        "--name",
        "Notes",
    ]
    assert sent["prompt"] == "hello"
    assert sent["cwd"].lower() == str(tmp_path).lower()
    # The view now holds the messages of the session file, not those made during the run.
    spans = conversation._conversation.document.spans
    assert not any(span.message.id.startswith("local-") for span in spans)


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
    assert conversation._conversations.agent == OPUS  # the agent of the conversation is not changed


def test_the_end_of_an_answer_is_a_sound_by_default_and_progress_follows_its_category(
    conversation: MainWindow,
) -> None:
    conversation._settings.set_destination(PROGRESS, Destination.NONE)
    sink, player = RecordingMessageSink(), RecordingSoundPlayer()
    conversation._feedback.announcements.message_sink = sink
    conversation._feedback.announcements.sound_player = player
    conversation._prompt.SetValue("hello")
    conversation.send_prompt(alternative=False)
    _wait_until_idle(conversation)
    assert sink.messages == []  # no progress, and the end is a sound
    assert player.played == [Destination.SOUND_1]
    # Nothing else was written: the status bar went back to "Ready" with the gauge of the fake CLI.
    assert conversation.GetStatusBar().GetStatusText(2) == "Ready, gauge at 50 %"


def test_a_failure_is_shown_in_a_dialog_and_in_the_status_bar(
    conversation: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_CLAUDE", "crash")
    errors = _Errors(conversation)
    sink = RecordingMessageSink()
    conversation._feedback.announcements.message_sink = sink
    conversation._prompt.SetValue("hello")
    conversation.send_prompt(alternative=False)
    _wait_until_idle(conversation)
    assert len(errors.messages) == 1
    assert "not logged in" in errors.messages[0]
    status = conversation.GetStatusBar().GetStatusText(2)
    assert status.startswith("Claude could not answer: fake claude: not logged in")
    assert not any("could not answer" in message for message in sink.messages)  # the dialog speaks
    assert conversation.can_send


def test_a_missing_claude_keeps_the_prompt(
    conversation: MainWindow, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    conversation._run.runner = ClaudeRunner()
    errors = _Errors(conversation)
    conversation._prompt.SetValue("hello")
    conversation.send_prompt(alternative=False)
    assert len(errors.messages) == 1
    assert conversation._prompt.GetValue() == "hello"
    assert not conversation._run.busy
    assert conversation._conversation.GetValue() == ""


def test_interrupting_stops_claude(
    conversation: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_CLAUDE", "slow")
    errors = _Errors(conversation)
    sink = RecordingMessageSink()
    conversation._feedback.announcements.message_sink = sink
    conversation._settings.set_destination(END_OF_ANSWER, Destination.MESSAGE)
    conversation._prompt.SetValue("hello")
    conversation.send_prompt(alternative=False)
    assert conversation._menu.interrupt_item.IsEnabled()
    conversation._on_interrupt(wx.CommandEvent())
    _wait_until_idle(conversation)
    assert sink.messages[-2:] == ["Interrupting Claude.", "Claude was interrupted."]
    assert errors.messages == []
    assert not conversation._menu.interrupt_item.IsEnabled()


def test_nothing_is_sent_without_a_conversation(window: MainWindow) -> None:
    window._prompt.SetValue("hello")
    window.send_prompt(alternative=False)
    assert window._conversation.GetValue() == ""


def test_the_first_status_field_gives_the_position_among_the_prompts(
    conversation: MainWindow,
) -> None:
    assert conversation.GetStatusBar().GetStatusText(0) == ""  # no prompt yet
    _send(conversation, "one")
    _send(conversation, "two")
    view = conversation._conversation
    view.focus_last_prompt()
    assert conversation.GetStatusBar().GetStatusText(0) == "Message 2 of 2"
    view.SetInsertionPoint(0)
    view.report_position()
    assert conversation.GetStatusBar().GetStatusText(0) == "Message 1 of 2"
    assert conversation.GetStatusBar().GetStatusText(2) != ""  # the messages: last field


def _make_tasks(conversation: MainWindow) -> None:
    folder = claude_config_dir() / "tasks" / conversation.conversation_id
    folder.mkdir(parents=True)
    for number, subject in ((1, "Alpha"), (2, "Beta")):
        task = {"id": str(number), "subject": subject, "status": "pending"}
        (folder / f"{number}.json").write_text(json.dumps(task), encoding="utf-8")


def test_a_step_put_in_progress_is_said_and_kept_in_the_second_status_field(
    conversation: MainWindow,
) -> None:
    _make_tasks(conversation)
    sink = RecordingMessageSink()
    conversation._feedback.announcements.message_sink = sink
    status = conversation.GetStatusBar()
    assert status.GetStatusText(1) == ""
    run = conversation._run
    run.on_event(ToolUsed("t1", "TaskUpdate", {"taskId": "2", "status": "in_progress"}))
    assert status.GetStatusText(1) == "Step 2 of 2: Beta"
    assert sink.messages == ["Step 2 of 2: Beta"]
    run.on_event(ToolUsed("t2", "TaskUpdate", {"taskId": "2", "status": "completed"}))
    assert sink.messages[-1] == "Claude uses the tool TaskUpdate."  # not a step start
    assert status.GetStatusText(1) == "Step 2 of 2: Beta"
    run.on_event(TurnResult(False, "success", "", None, None, None, None))
    run.on_event(TurnEnded(0, False, "", []))
    assert status.GetStatusText(1) == ""  # waiting for the next prompt


def test_a_step_that_is_not_in_the_list_is_normal_progress(conversation: MainWindow) -> None:
    sink = RecordingMessageSink()
    conversation._feedback.announcements.message_sink = sink
    tool = ToolUsed("t1", "TaskUpdate", {"taskId": "9", "status": "in_progress"})
    conversation._run.on_event(tool)
    assert sink.messages == ["Claude uses the tool TaskUpdate."]
    assert conversation.GetStatusBar().GetStatusText(1) == ""


def test_the_runner_uses_the_claude_file_chosen_in_the_preferences(window: MainWindow) -> None:
    assert window._run.runner.claude_path == ""
    window._settings.claude_auto_search = False
    window._settings.claude_path = "C:/tools/claude.exe"
    window._apply_claude_path()
    assert window._run.runner.claude_path == "C:/tools/claude.exe"
    window._settings.claude_auto_search = True
    window._apply_claude_path()
    assert window._run.runner.claude_path == ""


def test_renaming_a_conversation_that_was_answered_goes_through_the_cli(
    conversation: MainWindow, claude_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _send(conversation, "hello")
    screen = conversation._conversations._view
    monkeypatch.setattr(screen, "ask_name", lambda _title, _proposal: "Renamed")
    conversation._conversations.rename()
    assert conversation._conversations.name == "Renamed"
    assert conversation.GetTitle().startswith("Renamed - ")
    session = claude_config / "projects" / "fake" / f"{conversation.conversation_id}.jsonl"
    titles = [
        json.loads(line)["customTitle"]
        for line in session.read_text(encoding="utf-8").splitlines()
        if '"custom-title"' in line
    ]
    assert titles == ["Notes", "Renamed"]  # the first message named it, the rename followed
