"""The presenter of a message sent to Claude, with a fake view: no wx, no window."""

from collections.abc import Callable
from pathlib import Path

import pytest
from fake_claude_files import FakeClaudeFiles

from wxclaude.core.claude.events import (
    AssistantText,
    PermissionExpired,
    PermissionRequest,
    RateLimit,
    RateWindow,
    RunEvent,
    Thinking,
    ToolUsed,
    TurnEnded,
    TurnResult,
)
from wxclaude.core.claude.permissions import Choice, Decision
from wxclaude.core.claude.runner import ClaudeRunner
from wxclaude.core.claude.tasks import Task
from wxclaude.core.claude.usage import UsageTracker
from wxclaude.core.config.settings import Settings
from wxclaude.core.conversation.messages import Message
from wxclaude.core.speech.announcements import Announce
from wxclaude.presenters.run_presenter import RunLinks, RunPresenter
from wxclaude.presenters.shared import Shared

pytestmark = pytest.mark.unit

CONVERSATION = "d278c1fc-1d73-4c16-a899-5bdb1831fe5c"
SUCCESS = TurnResult(False, "success", "", None, None, None, None)


class FakeView:
    """Records what the presenter shows; answers the permission questions with ``decisions``."""

    def __init__(self, *decisions: Decision) -> None:
        self.messages: list[Message] = []
        self.said: list[tuple[Announce, dict[str, object]]] = []
        self.status: list[str] = []
        self.steps: list[str] = []
        self.errors: list[str] = []
        self.asked: list[PermissionRequest] = []
        self.closed: list[str] = []
        self.sessions: list[list[Message]] = []
        self._decisions = list(decisions)

    def call_after(self, function: Callable[[RunEvent], None], event: RunEvent) -> None:
        function(event)

    def append_message(self, message: Message) -> None:
        self.messages.append(message)

    def show_session(self, messages: list[Message]) -> None:
        self.sessions.append(messages)

    def ask_permission(self, request: PermissionRequest) -> Decision:
        self.asked.append(request)
        return self._decisions.pop(0)

    def close_permission(self, request_id: str) -> None:
        self.closed.append(request_id)

    def say(self, announce: Announce, **values: object) -> None:
        self.said.append((announce, values))

    def set_status(self, text: str) -> None:
        self.status.append(text)

    def show_step(self, text: str) -> None:
        self.steps.append(text)

    def show_error(self, message: str) -> None:
        self.errors.append(message)

    def announces(self) -> list[Announce]:
        return [announce for announce, _values in self.said]


class FakeRunner(ClaudeRunner):
    """Records the answers instead of writing to a process."""

    def __init__(self) -> None:
        super().__init__()
        self.answers: list[tuple[str, str]] = []

    def allow(self, request: PermissionRequest) -> None:
        self.answers.append(("allow", request.request_id))

    def deny(self, request: PermissionRequest, message: str) -> None:
        self.answers.append(("deny", message))


def _presenter(
    view: FakeView, workspace: Path, files: FakeClaudeFiles | None = None
) -> tuple[RunPresenter, FakeRunner]:
    runner = FakeRunner()
    shared = Shared(Settings.load(None), UsageTracker(), files or FakeClaudeFiles())
    links = RunLinks(
        workspace=lambda: workspace,
        conversation_id=lambda: CONVERSATION,
        conversation_name=lambda: "Notes",
        is_closing=lambda: False,
        state_changed=lambda: None,
    )
    return RunPresenter(view, runner, shared, links), runner


def test_progress_is_said_once_and_the_answer_is_shown(tmp_path: Path) -> None:
    view = FakeView()
    presenter, _runner = _presenter(view, tmp_path)
    for event in (Thinking(), Thinking(), AssistantText(" Hi ", "m"), SUCCESS):
        presenter.on_event(event)
    presenter.on_event(TurnEnded(0, False, "", []))
    assert view.announces() == [
        Announce.CLAUDE_THINKING,
        Announce.CLAUDE_ANSWERING,
        Announce.CLAUDE_DONE,
    ]
    assert [message.text for message in view.messages] == ["Hi"]
    assert view.steps == [""]  # the step field is emptied at the end of the turn
    assert view.status == ["Ready"]  # no gauge known yet


def _gauges(five_hour: float, week: float = 0.1) -> RateLimit:
    windows = (RateWindow("five_hour", five_hour, 1), RateWindow("seven_day", week, 2))
    return RateLimit("allowed", "five_hour", windows)


def test_the_status_bar_says_ready_with_the_gauge_of_the_five_hours(tmp_path: Path) -> None:
    view = FakeView()
    presenter, _runner = _presenter(view, tmp_path)
    presenter.on_event(_gauges(0.5))
    presenter.on_event(SUCCESS)
    presenter.on_event(TurnEnded(0, False, "", []))
    assert view.status == ["Ready, gauge at 50 %"]


def test_an_alert_is_said_once_per_crossing_even_when_the_window_stays_open(
    tmp_path: Path,
) -> None:
    view = FakeView()
    presenter, _runner = _presenter(view, tmp_path)

    def alerts() -> list[tuple[Announce, dict[str, object]]]:
        return [
            item
            for item in view.said
            if item[0] in (Announce.GAUGE_FIVE_HOUR, Announce.GAUGE_WEEKLY)
        ]

    presenter.on_event(_gauges(0.5))
    assert alerts() == []
    presenter.on_event(_gauges(0.92))
    presenter.on_event(_gauges(0.95))  # still over: not said again
    assert alerts() == [(Announce.GAUGE_FIVE_HOUR, {"percent": 92})]
    presenter.on_event(_gauges(0.05))  # a new window of 5 hours, back near 0
    presenter.on_event(_gauges(0.93, week=0.8))
    assert alerts() == [
        (Announce.GAUGE_FIVE_HOUR, {"percent": 92}),
        (Announce.GAUGE_FIVE_HOUR, {"percent": 93}),
        (Announce.GAUGE_WEEKLY, {"percent": 80}),
    ]


def test_a_failed_turn_goes_to_the_status_bar_and_a_dialog(tmp_path: Path) -> None:
    view = FakeView()
    presenter, _runner = _presenter(view, tmp_path)
    presenter.on_event(TurnEnded(2, False, "not logged in", []))
    assert view.status == ["Claude could not answer: not logged in"]  # not "Ready"
    assert view.errors == ["Claude could not answer.\nnot logged in"]
    assert Announce.CLAUDE_DONE not in view.announces()


def test_a_permission_is_asked_then_answered(tmp_path: Path) -> None:
    view = FakeView(Decision(Choice.ALLOW), Decision(Choice.DENY, "No"))
    presenter, runner = _presenter(view, tmp_path)
    presenter.on_event(PermissionRequest("r1", "Bash", "t", {}, "", "", ""))
    presenter.on_event(PermissionRequest("r2", "Write", "t", {}, "", "", ""))
    assert runner.answers == [("allow", "r1"), ("deny", "No")]
    assert view.announces() == [
        Announce.PERMISSION_ASKED,
        Announce.PERMISSION_GRANTED,
        Announce.PERMISSION_ASKED,
        Announce.PERMISSION_REFUSED,
    ]


def test_always_allow_writes_the_rule_and_is_not_asked_again_in_the_message(
    tmp_path: Path,
) -> None:
    view = FakeView(Decision(Choice.ALLOW_ALWAYS))
    files = FakeClaudeFiles()
    presenter, runner = _presenter(view, tmp_path, files)
    request = PermissionRequest("r1", "Bash", "t", {}, "", "", "Bash(touch x)")
    presenter.on_event(request)
    presenter.on_event(PermissionRequest("r2", "Bash", "t", {}, "", "", "Bash(touch x)"))
    assert len(view.asked) == 1
    assert runner.answers == [("allow", "r1"), ("allow", "r2")]
    assert files.rules == [(tmp_path, "Bash(touch x)")]


def test_an_expired_question_is_closed_and_not_answered(tmp_path: Path) -> None:
    view = FakeView()
    presenter, runner = _presenter(view, tmp_path)
    request = PermissionRequest("r1", "Write", "t", {}, "", "", "")

    def ask(asked: PermissionRequest) -> Decision:
        presenter.on_event(PermissionExpired(asked.request_id, asked.tool_name))  # while open
        return Decision(Choice.ALLOW)

    view.ask_permission = ask  # type: ignore[method-assign]
    presenter.on_event(request)
    assert view.closed == ["r1"]
    assert runner.answers == []
    assert Announce.PERMISSION_EXPIRED in view.announces()


def test_a_step_put_in_progress_replaces_the_tool_progress(tmp_path: Path) -> None:
    files = FakeClaudeFiles(tasks={CONVERSATION: [Task("1", "Alpha", "", "pending")]})
    view = FakeView()
    presenter, _runner = _presenter(view, tmp_path, files)
    presenter.on_event(ToolUsed("t", "TaskUpdate", {"taskId": "1", "status": "in_progress"}))
    assert view.steps == ["Step 1 of 1: Alpha"]
    assert view.said == [(Announce.STEP_STARTED, {"number": 1, "total": 1, "subject": "Alpha"})]
    presenter.on_event(ToolUsed("t2", "Read", {}))
    assert view.said[-1] == (Announce.CLAUDE_USING_TOOL, {"tool": "Read"})


def test_nothing_is_started_without_a_workspace() -> None:
    view = FakeView()
    runner = FakeRunner()
    links = RunLinks(lambda: None, lambda: CONVERSATION, lambda: "", lambda: False, lambda: None)
    shared = Shared(Settings.load(None), UsageTracker(), FakeClaudeFiles())
    presenter = RunPresenter(view, runner, shared, links)
    assert not presenter.start("hello", Settings.load(None).default_agent)
    assert not presenter.busy
    assert view.messages == []
