import json
import sys
import threading
from pathlib import Path

import pytest

from wxclaude.core.claude.events import (
    AssistantText,
    PermissionDenied,
    RunEvent,
    SessionInit,
    ToolUsed,
    TurnEnded,
    TurnResult,
)
from wxclaude.core.claude.permission_channel import StdioChannel
from wxclaude.core.claude.runner import ClaudeRunner, RunRequest, build_arguments, find_claude
from wxclaude.core.config.agents import Agent
from wxclaude.core.errors import ClaudeNotFoundError, RunnerError

pytestmark = pytest.mark.unit

FAKE = Path(__file__).resolve().parents[2] / "fakes" / "fake_claude.py"
AGENT = Agent(model="haiku", effort="low", permission_mode="manual")


class Collector:
    """Receives the events (from other threads) and waits for the last one."""

    def __init__(self) -> None:
        self.events: list[RunEvent] = []
        self.done = threading.Event()

    def __call__(self, event: RunEvent) -> None:
        self.events.append(event)
        if isinstance(event, TurnEnded):
            self.done.set()

    def wait(self, timeout: float = 30) -> None:
        assert self.done.wait(timeout), "the run did not end"

    @property
    def ended(self) -> TurnEnded:
        last = self.events[-1]
        assert isinstance(last, TurnEnded)
        return last


def _request(tmp_path: Path, *, resume: bool = False, agent: Agent = AGENT) -> RunRequest:
    return RunRequest("Hello ✓", agent, "11111111-1111-4111-8111-111111111111", resume, tmp_path)


def _runner() -> ClaudeRunner:
    return ClaudeRunner([sys.executable, str(FAKE)])


def test_the_arguments_of_a_new_and_of_a_resumed_conversation(tmp_path: Path) -> None:
    new = build_arguments(_request(tmp_path), StdioChannel())
    assert new[-2:] == ["--session-id", "11111111-1111-4111-8111-111111111111"]
    assert new[new.index("--model") + 1] == "haiku"
    assert new[new.index("--effort") + 1] == "low"
    assert new[new.index("--permission-mode") + 1] == "manual"
    assert "--verbose" in new
    assert build_arguments(_request(tmp_path, resume=True), StdioChannel())[-2] == "--resume"


def test_an_incomplete_agent_is_refused(tmp_path: Path) -> None:
    with pytest.raises(RunnerError):
        build_arguments(_request(tmp_path, agent=Agent(model="haiku")), StdioChannel())


def test_a_run_reports_its_events_in_order_and_ends_with_turn_ended(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = tmp_path / "log.json"
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    collector = Collector()
    runner = _runner()
    runner.start(_request(tmp_path), collector)
    collector.wait()
    kinds = [type(event) for event in collector.events]
    assert kinds[0] is SessionInit
    assert kinds[-1] is TurnEnded
    assert kinds.index(ToolUsed) < kinds.index(AssistantText) < kinds.index(TurnResult)
    text = next(e for e in collector.events if isinstance(e, AssistantText))
    assert text.text == "Echo: Hello ✓"  # the prompt went through stdin, with its accents
    assert collector.ended.exit_code == 0
    assert not collector.ended.interrupted
    sent = json.loads(log.read_text(encoding="utf-8"))
    assert sent["cwd"].lower() == str(tmp_path).lower()
    assert not runner.is_running


def test_a_permission_denial_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_CLAUDE", "denied")
    collector = Collector()
    _runner().start(_request(tmp_path), collector)
    collector.wait()
    assert PermissionDenied("Bash", "Bash needs permission") in collector.events


def test_an_error_result_and_a_crash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_CLAUDE", "error")
    failed = Collector()
    _runner().start(_request(tmp_path), failed)
    failed.wait()
    result = next(e for e in failed.events if isinstance(e, TurnResult))
    assert result.is_error
    assert failed.ended.exit_code == 1

    monkeypatch.setenv("FAKE_CLAUDE", "crash")
    crashed = Collector()
    _runner().start(_request(tmp_path), crashed)
    crashed.wait()
    assert crashed.ended.exit_code == 2
    assert "not logged in" in crashed.ended.stderr
    assert not any(isinstance(e, TurnResult) for e in crashed.events)


def test_lines_that_are_not_json_are_kept_as_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_CLAUDE", "garbage")
    collector = Collector()
    _runner().start(_request(tmp_path), collector)
    collector.wait()
    assert len(collector.ended.diagnostics) == 1
    assert any(isinstance(e, TurnResult) for e in collector.events)


def test_interrupting_ends_the_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_CLAUDE", "slow")
    collector = Collector()
    runner = _runner()
    runner.start(_request(tmp_path), collector)
    while not any(isinstance(e, SessionInit) for e in collector.events):
        assert not collector.done.is_set(), "the run ended by itself"
        threading.Event().wait(0.05)
    assert runner.is_running
    runner.interrupt()
    collector.wait()
    assert collector.ended.interrupted
    assert not runner.is_running
    runner.interrupt()  # nothing runs: nothing happens


def test_only_one_message_runs_at_a_time(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_CLAUDE", "slow")
    collector = Collector()
    runner = _runner()
    runner.start(_request(tmp_path), collector)
    try:
        with pytest.raises(RunnerError):
            runner.start(_request(tmp_path), Collector())
    finally:
        runner.interrupt()
        collector.wait()


def test_a_missing_executable_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(ClaudeNotFoundError):
        ClaudeRunner().start(_request(tmp_path), Collector())
    with pytest.raises(RunnerError):
        ClaudeRunner([str(tmp_path / "nothing")]).start(_request(tmp_path), Collector())


def test_a_chosen_claude_file_is_used_instead_of_the_path(tmp_path: Path) -> None:
    claude = tmp_path / "claude.exe"
    claude.write_text("", encoding="utf-8")
    assert find_claude(str(claude)) == [str(claude)]


def test_a_chosen_claude_file_that_is_missing_is_reported(tmp_path: Path) -> None:
    with pytest.raises(ClaudeNotFoundError, match="does not exist"):
        find_claude(str(tmp_path / "nowhere.exe"))


def test_the_name_is_given_to_the_cli_by_the_first_message_only(tmp_path: Path) -> None:
    first = RunRequest("Hello", AGENT, "s-1", False, tmp_path, "My notes")
    arguments = build_arguments(first, StdioChannel())
    assert arguments[-4:] == ["--session-id", "s-1", "--name", "My notes"]
    later = RunRequest("Hello", AGENT, "s-1", True, tmp_path, "My notes")
    assert "--name" not in build_arguments(later, StdioChannel())
    unnamed = RunRequest("Hello", AGENT, "s-1", False, tmp_path)
    assert "--name" not in build_arguments(unnamed, StdioChannel())


def test_the_first_message_of_a_branch_forks_the_conversation_it_comes_from(
    tmp_path: Path,
) -> None:
    branch = RunRequest("Hello", AGENT, "s-2", False, tmp_path, "Notes branche 1", "s-1")
    arguments = build_arguments(branch, StdioChannel())
    assert arguments[-7:] == [
        "--resume",
        "s-1",
        "--fork-session",
        "--session-id",
        "s-2",
        "--name",
        "Notes branche 1",
    ]
    later = RunRequest("Hello", AGENT, "s-2", True, tmp_path, "Notes branche 1", "s-1")
    assert build_arguments(later, StdioChannel())[-2:] == ["--resume", "s-2"]  # no fork again


def test_a_session_is_renamed_by_the_rename_command_of_the_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "config"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config))
    log = tmp_path / "log.json"
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    _runner().rename_session("s-1", "New name", tmp_path)
    arguments = json.loads(log.read_text(encoding="utf-8"))["arguments"]
    assert arguments[:2] == ["-p", "/rename New name"]
    assert arguments[arguments.index("--resume") + 1] == "s-1"
    written = (config / "projects" / "fake" / "s-1.jsonl").read_text(encoding="utf-8")
    assert json.loads(written)["customTitle"] == "New name"


def test_a_rename_that_the_cli_refuses_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_CLAUDE", "rename_fails")
    with pytest.raises(RunnerError, match="No such session"):
        _runner().rename_session("s-1", "New name", tmp_path)


def test_the_runner_knows_whether_claude_can_be_started(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert ClaudeRunner([sys.executable]).is_available()  # a command given: the tests
    runner = ClaudeRunner()
    monkeypatch.setattr("wxclaude.core.claude.runner.shutil.which", lambda _name: None)
    assert not runner.is_available()  # nothing in the PATH
    monkeypatch.setattr("wxclaude.core.claude.runner.shutil.which", lambda _name: "/x/claude")
    assert runner.is_available()
    runner.claude_path = str(tmp_path / "missing.exe")
    assert not runner.is_available()  # the file chosen by hand does not exist
    (tmp_path / "claude.exe").write_text("", encoding="utf-8")
    runner.claude_path = str(tmp_path / "claude.exe")
    assert runner.is_available()
