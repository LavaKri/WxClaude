import json
import sys
import threading
from pathlib import Path

import pytest

from wxclaude.core.claude import runner as runner_module
from wxclaude.core.claude.events import GaugesRead, RunEvent
from wxclaude.core.claude.runner import ClaudeRunner
from wxclaude.core.errors import ClaudeNotFoundError, RunnerError

pytestmark = pytest.mark.unit

FAKE = Path(__file__).resolve().parents[2] / "fakes" / "fake_claude.py"


class Reading:
    """Receives the end of a reading (from another thread) and waits for it."""

    def __init__(self) -> None:
        self.events: list[RunEvent] = []
        self.done = threading.Event()

    def __call__(self, event: RunEvent) -> None:
        self.events.append(event)
        self.done.set()

    def wait(self, timeout: float = 30) -> GaugesRead:
        assert self.done.wait(timeout), "the reading did not end"
        (event,) = self.events
        assert isinstance(event, GaugesRead)
        return event


def _runner() -> ClaudeRunner:
    return ClaudeRunner([sys.executable, str(FAKE)])


def test_the_gauges_are_read_without_a_session_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = tmp_path / "log.json"
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    runner, reading = _runner(), Reading()
    runner.read_usage(tmp_path, reading)
    windows = reading.wait().windows
    assert [(w.name, w.utilization) for w in windows] == [("five_hour", 0.96), ("seven_day", 0.67)]
    arguments = json.loads(log.read_text(encoding="utf-8"))["arguments"]
    assert arguments == ["-p", "/usage", "--no-session-persistence", "--output-format", "json"]
    assert not runner.is_running


@pytest.mark.parametrize("scenario", ["usage_fails", "usage_garbage"])
def test_a_failure_or_an_unknown_text_gives_no_gauge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scenario: str
) -> None:
    monkeypatch.setenv("FAKE_CLAUDE", scenario)
    runner, reading = _runner(), Reading()
    runner.read_usage(tmp_path, reading)
    assert reading.wait().windows == ()
    assert not runner.is_running


def test_a_cli_that_does_not_answer_is_stopped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_CLAUDE", "usage_slow")
    monkeypatch.setattr(runner_module, "_USAGE_WAIT_SECONDS", 1)
    runner, reading = _runner(), Reading()
    runner.read_usage(tmp_path, reading)
    assert reading.wait().windows == ()
    assert not runner.is_running


def test_interrupt_stops_the_reading(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_CLAUDE", "usage_slow")
    runner, reading = _runner(), Reading()
    runner.read_usage(tmp_path, reading)
    assert runner.is_running
    with pytest.raises(RunnerError):
        runner.read_usage(tmp_path, Reading())  # one process at a time
    runner.interrupt()
    assert reading.wait(10).windows == ()
    assert not runner.is_running


def test_a_missing_cli_is_reported(tmp_path: Path) -> None:
    runner = ClaudeRunner()
    runner.claude_path = str(tmp_path / "missing.exe")
    with pytest.raises(ClaudeNotFoundError):
        runner.read_usage(tmp_path, Reading())
