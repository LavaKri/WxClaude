import json
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from wxclaude.core.agents import Agent
from wxclaude.core.errors import RunnerError
from wxclaude.core.events import PermissionRequest, RunEvent, ToolResult, TurnEnded
from wxclaude.core.permission_channel import HOOK, StdioChannel, make_channel
from wxclaude.core.runner import ClaudeRunner, RunRequest, build_arguments

pytestmark = pytest.mark.unit

FAKE = Path(__file__).resolve().parent.parent / "fakes" / "fake_claude.py"
AGENT = Agent(model="haiku", effort="low", permission_mode="manual")
SESSION = "11111111-1111-4111-8111-111111111111"


def _request(tmp_path: Path, *, resume: bool = False) -> RunRequest:
    return RunRequest("Hello", AGENT, SESSION, resume, tmp_path)


def _runner() -> ClaudeRunner:
    return ClaudeRunner([sys.executable, str(FAKE)])


class Asker:
    """Receives the events and answers the permission questions like a user would."""

    def __init__(self, runner: ClaudeRunner, *, allow: bool, message: str = "") -> None:
        self.events: list[RunEvent] = []
        self.requests: list[PermissionRequest] = []
        self.done = threading.Event()
        self._runner = runner
        self._allow = allow
        self._message = message

    def __call__(self, event: RunEvent) -> None:
        if isinstance(event, PermissionRequest):
            self.requests.append(event)
            if self._allow:
                self._runner.allow(event)
            else:
                self._runner.deny(event, self._message)
        self.events.append(event)
        if isinstance(event, TurnEnded):
            self.done.set()

    def wait(self) -> TurnEnded:
        assert self.done.wait(30), "the run did not end"
        ended = self.events[-1]
        assert isinstance(ended, TurnEnded)
        return ended

    @property
    def tool_result(self) -> ToolResult:
        return next(e for e in self.events if isinstance(e, ToolResult))


def test_the_cli_is_started_in_stream_json_with_the_stdio_permission_tool(tmp_path: Path) -> None:
    arguments = build_arguments(_request(tmp_path), StdioChannel())
    assert arguments[arguments.index("--input-format") + 1] == "stream-json"
    assert arguments[arguments.index("--output-format") + 1] == "stream-json"
    assert arguments[arguments.index("--permission-prompt-tool") + 1] == "stdio"
    assert "--allowedTools" not in arguments


def test_a_permission_question_can_be_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_CLAUDE", "permission")
    log = tmp_path / "log.json"
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    runner = _runner()
    asker = Asker(runner, allow=True)
    runner.start(_request(tmp_path), asker)
    ended = asker.wait()
    (question,) = asker.requests
    assert question.tool_name == "Bash"
    assert question.suggested_rule == "Bash(touch fake.txt)"
    assert question.input["command"] == "touch fake.txt"
    assert not asker.tool_result.is_error
    assert ended.exit_code == 0  # stdin was closed after the result, so the fake could end
    response = json.loads(Path(str(log) + ".responses").read_text(encoding="utf-8"))
    assert response["type"] == "control_response"
    assert response["response"]["request_id"] == "req-1"
    assert response["response"]["response"] == {"behavior": "allow", "updatedInput": question.input}


def test_a_permission_question_can_be_denied_with_an_explanation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_CLAUDE", "permission")
    log = tmp_path / "log.json"
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    runner = _runner()
    asker = Asker(runner, allow=False, message="Not in this folder")
    runner.start(_request(tmp_path), asker)
    asker.wait()
    assert asker.tool_result.is_error
    response = json.loads(Path(str(log) + ".responses").read_text(encoding="utf-8"))
    assert response["response"]["response"] == {"behavior": "deny", "message": "Not in this folder"}


def test_a_rule_of_the_settings_file_means_no_question(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_CLAUDE", "permission")
    settings = tmp_path / ".claude" / "settings.local.json"
    settings.parent.mkdir()
    settings.write_text(
        json.dumps({"permissions": {"allow": ["Bash(touch fake.txt)"]}}), encoding="utf-8"
    )
    runner = _runner()
    asker = Asker(runner, allow=False)
    runner.start(_request(tmp_path), asker)
    asker.wait()
    assert asker.requests == []
    assert not asker.tool_result.is_error


def _hook_runner() -> ClaudeRunner:
    runner = _runner()
    runner.permission_channel = HOOK
    return runner


def test_the_hook_channel_passes_settings_instead_of_the_permission_tool(tmp_path: Path) -> None:
    channel = make_channel(HOOK, lambda _event: None, 90)
    try:
        arguments = build_arguments(_request(tmp_path), channel)
    finally:
        channel.close()
    assert "--permission-prompt-tool" not in arguments
    assert arguments[arguments.index("--input-format") + 1] == "stream-json"
    assert json.loads(arguments[arguments.index("--settings") + 1])["hooks"]["PermissionRequest"]


def test_through_the_hook_a_permission_question_can_be_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_CLAUDE", "permission")
    log = tmp_path / "log.json"
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    runner = _hook_runner()
    asker = Asker(runner, allow=True)
    runner.start(_request(tmp_path), asker)
    ended = asker.wait()
    (question,) = asker.requests
    assert question.tool_name == "Bash"
    assert question.suggested_rule == "Bash(touch fake.txt)"
    assert not asker.tool_result.is_error
    assert ended.exit_code == 0
    reply = json.loads(Path(str(log) + ".responses").read_text(encoding="utf-8"))
    assert reply["hookSpecificOutput"]["decision"] == {"behavior": "allow"}


def test_through_the_hook_a_permission_question_can_be_denied_with_an_explanation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_CLAUDE", "permission")
    log = tmp_path / "log.json"
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    runner = _hook_runner()
    asker = Asker(runner, allow=False, message="Not in this folder")
    runner.start(_request(tmp_path), asker)
    asker.wait()
    assert asker.tool_result.is_error
    reply = json.loads(Path(str(log) + ".responses").read_text(encoding="utf-8"))
    assert reply["hookSpecificOutput"]["decision"] == {
        "behavior": "deny",
        "message": "Not in this folder",
    }


def test_the_hook_server_is_gone_when_the_message_has_ended(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_CLAUDE", "permission")
    log = tmp_path / "log.json"
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    runner = _hook_runner()
    asker = Asker(runner, allow=True)
    runner.start(_request(tmp_path), asker)
    asker.wait()
    given = json.loads(log.read_text(encoding="utf-8"))["arguments"]
    settings = json.loads(given[given.index("--settings") + 1])
    url = settings["hooks"]["PermissionRequest"][0]["hooks"][0]["url"]
    with pytest.raises(urllib.error.URLError):  # the connection is refused
        urllib.request.urlopen(url, data=b"{}", timeout=5)


def test_answering_when_nothing_runs_is_an_error() -> None:
    question = PermissionRequest("r", "Bash", "t", {}, "", "", "")
    with pytest.raises(RunnerError):
        _runner().allow(question)
    with pytest.raises(RunnerError):
        _runner().deny(question, "no")
