"""The presenter of a message sent to Claude, with a fake view: no wx, no window."""

import re
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
    SessionInit,
    Thinking,
    ToolUsed,
    TurnEnded,
    TurnResult,
)
from wxclaude.core.claude.permissions import (
    PLAN_QUESTIONS_REFUSAL,
    PLAN_REFUSAL,
    Choice,
    Decision,
)
from wxclaude.core.claude.questions import Question
from wxclaude.core.claude.runner import ClaudeRunner, RunRequest
from wxclaude.core.claude.tasks import Task
from wxclaude.core.claude.usage import UsageTracker
from wxclaude.core.config.agents import Agent
from wxclaude.core.config.settings import Settings
from wxclaude.core.config.workspace_stats import WorkspaceStats
from wxclaude.core.conversation.messages import Message, Usage
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
        self.waits: list[str] = []  # the waiting text given with each question
        self.closed: list[str] = []
        self.sessions: list[list[Message]] = []
        self._decisions = list(decisions)
        self.questions: list[list[Question]] = []  # the structured questions asked
        self.question_answers: dict[str, list[str]] | None = None  # what the user answers

    def call_after(self, function: Callable[[RunEvent], None], event: RunEvent) -> None:
        function(event)

    def append_message(self, message: Message) -> None:
        self.messages.append(message)

    def show_session(self, messages: list[Message]) -> None:
        self.sessions.append(messages)

    def ask_permission(self, request: PermissionRequest, wait_text: str = "") -> Decision:
        self.asked.append(request)
        self.waits.append(wait_text)
        return self._decisions.pop(0)

    def ask_questions(self, questions: list[Question]) -> dict[str, list[str]] | None:
        self.questions.append(questions)
        return self.question_answers

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
    """Records the messages started and the answers instead of running a process."""

    def __init__(self) -> None:
        super().__init__()
        self.answers: list[tuple[str, str]] = []
        self.requests: list[RunRequest] = []
        self.answered: list[dict[str, list[str]]] = []  # answers to structured questions

    def start(self, request: RunRequest, on_event: Callable[[RunEvent], None]) -> None:
        self.requests.append(request)

    def allow(self, request: PermissionRequest) -> None:
        self.answers.append(("allow", request.request_id))

    def answer_questions(self, request: PermissionRequest, answers: dict[str, list[str]]) -> None:
        self.answered.append(answers)

    def deny(self, request: PermissionRequest, message: str) -> None:
        self.answers.append(("deny", message))


def _presenter(
    view: FakeView,
    workspace: Path,
    files: FakeClaudeFiles | None = None,
    fork_from: str = "",
    stats: WorkspaceStats | None = None,
) -> tuple[RunPresenter, FakeRunner]:
    runner = FakeRunner()
    shared = Shared(Settings.load(None), UsageTracker(), files or FakeClaudeFiles())
    links = RunLinks(
        workspace=lambda: workspace,
        conversation_id=lambda: CONVERSATION,
        conversation_name=lambda: "Notes",
        fork_from=lambda: fork_from,
        is_closing=lambda: False,
        state_changed=lambda: None,
        stats=lambda: stats,
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


def test_a_rule_that_cannot_be_written_is_reported_and_the_tool_still_allowed(
    tmp_path: Path,
) -> None:
    view = FakeView(Decision(Choice.ALLOW_ALWAYS))
    files = FakeClaudeFiles(allow_error="Cannot read settings.local.json")
    presenter, runner = _presenter(view, tmp_path, files)
    presenter.on_event(PermissionRequest("r1", "Bash", "t", {}, "", "", "Bash(touch x)"))
    assert runner.answers == [("allow", "r1")]
    assert view.errors == ["The rule could not be saved.\nCannot read settings.local.json"]


def test_an_expired_question_is_closed_and_not_answered(tmp_path: Path) -> None:
    view = FakeView()
    presenter, runner = _presenter(view, tmp_path)
    request = PermissionRequest("r1", "Write", "t", {}, "", "", "")

    def ask(asked: PermissionRequest, _wait: str = "") -> Decision:
        presenter.on_event(PermissionExpired(asked.request_id, asked.tool_name))  # while open
        return Decision(Choice.ALLOW)

    view.ask_permission = ask  # type: ignore[assignment]
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
    links = RunLinks(
        workspace=lambda: None,
        conversation_id=lambda: CONVERSATION,
        conversation_name=lambda: "",
        fork_from=lambda: "",
        is_closing=lambda: False,
        state_changed=lambda: None,
    )
    shared = Shared(Settings.load(None), UsageTracker(), FakeClaudeFiles())
    presenter = RunPresenter(view, runner, shared, links)
    assert not presenter.start("hello", Settings.load(None).default_agent)
    assert not presenter.busy
    assert view.messages == []


def test_the_first_message_of_a_branch_names_the_conversation_it_comes_from(
    tmp_path: Path,
) -> None:
    presenter, runner = _presenter(FakeView(), tmp_path, fork_from="parent-id")
    assert presenter.start("hello", Settings.load(None).default_agent)
    (request,) = runner.requests
    assert (request.session_id, request.resume, request.fork_from) == (
        CONVERSATION,
        False,
        "parent-id",
    )
    assert request.name == "Notes"


def _ended(presenter: RunPresenter, duration_ms: int, cost: float | None = None) -> None:
    result = TurnResult(False, "success", "", Usage(3, 4, 0, 0), duration_ms, cost, 1)
    presenter.on_event(result)
    presenter.on_event(TurnEnded(0, False, "", []))


def test_a_finished_message_is_counted_in_the_statistics_with_the_model_that_answered(
    tmp_path: Path,
) -> None:
    stats = WorkspaceStats(tmp_path)
    presenter, _runner = _presenter(FakeView(), tmp_path, stats=stats)
    assert presenter.start("hello", Settings.load(None).default_agent)
    presenter.on_event(SessionInit("s", "claude-opus-5-5", "manual"))
    _ended(presenter, 2500)
    assert (stats.messages, stats.conversations, stats.activity_ms) == (1, [CONVERSATION], 2500)
    assert stats.tokens == Usage(3, 4, 0, 0)
    assert "claude-opus-5-5" in stats.models


def test_without_the_model_of_the_cli_the_one_that_was_asked_is_counted(tmp_path: Path) -> None:
    stats = WorkspaceStats(tmp_path)
    presenter, _runner = _presenter(FakeView(), tmp_path, stats=stats)
    agent = Settings.load(None).default_agent
    presenter.start("hello", agent)
    _ended(presenter, 100)
    assert list(stats.models) == [agent.model]


def test_the_time_spent_answering_a_permission_question_is_taken_off_the_time_of_work(
    tmp_path: Path,
) -> None:
    class Clock:
        seconds = 0.0

        def __call__(self) -> float:
            return self.seconds

    clock = Clock()
    view = FakeView(Decision(Choice.ALLOW))
    stats = WorkspaceStats(tmp_path)
    presenter, _runner = _presenter(view, tmp_path, stats=stats)
    presenter._stats._clock = clock  # the user takes 30 seconds to answer
    ask = view.ask_permission

    def slow_ask(request: PermissionRequest, wait_text: str = "") -> Decision:
        clock.seconds += 30
        return ask(request, wait_text)

    view.ask_permission = slow_ask  # type: ignore[method-assign]
    presenter.start("hello", Settings.load(None).default_agent)
    presenter.on_event(PermissionRequest("r1", "Bash", "t", {}, "", "", ""))
    _ended(presenter, 34400)
    assert stats.activity_ms == 4400


def test_an_interrupted_message_has_no_result_and_is_not_counted(tmp_path: Path) -> None:
    stats = WorkspaceStats(tmp_path)
    presenter, _runner = _presenter(FakeView(), tmp_path, stats=stats)
    presenter.start("hello", Settings.load(None).default_agent)
    presenter.on_event(TurnEnded(1, True, "", []))
    assert stats.messages == 0


def test_a_question_comes_with_no_waiting_time_through_stdio(tmp_path: Path) -> None:
    view = FakeView(Decision(Choice.ALLOW))
    presenter, _runner = _presenter(view, tmp_path)
    presenter.on_event(PermissionRequest("r1", "Bash", "t", {}, "", "", ""))
    assert view.waits == [""]


def test_a_question_through_the_hook_tells_when_the_cli_stops_waiting(tmp_path: Path) -> None:
    view = FakeView(Decision(Choice.ALLOW))
    presenter, runner = _presenter(view, tmp_path)
    runner.permission_channel = "hook"
    runner.hook_timeout_seconds = 600
    presenter.on_event(PermissionRequest("r1", "Bash", "t", {}, "", "", ""))
    (wait,) = view.waits
    assert re.fullmatch(
        r"Without an answer by \d\d:\d\d \(10 min\), Claude denies the tool\.", wait
    )


QUESTION_INPUT: dict[str, object] = {
    "questions": [
        {
            "question": "Which database?",
            "header": "Database",
            "options": [{"label": "SQLite", "description": "A file"}],
        }
    ]
}


def test_structured_questions_have_their_own_dialog_and_the_answers_go_back(
    tmp_path: Path,
) -> None:
    view = FakeView()
    view.question_answers = {"Which database?": ["SQLite"]}
    presenter, runner = _presenter(view, tmp_path)
    presenter.on_event(PermissionRequest("r1", "AskUserQuestion", "t", QUESTION_INPUT, "", "", ""))
    assert view.asked == []  # not the permission dialog
    (questions,) = view.questions
    assert [question.text for question in questions] == ["Which database?"]
    assert runner.answered == [{"Which database?": ["SQLite"]}]
    assert view.announces() == [Announce.QUESTION_ASKED, Announce.QUESTION_ANSWERED]


def test_refusing_the_structured_questions_denies_the_tool(tmp_path: Path) -> None:
    view = FakeView()
    presenter, runner = _presenter(view, tmp_path)  # question_answers is None: refused
    presenter.on_event(PermissionRequest("r1", "AskUserQuestion", "t", QUESTION_INPUT, "", "", ""))
    assert runner.answered == []
    assert runner.answers == [("deny", "The user denied this action.")]
    assert view.announces() == [Announce.QUESTION_ASKED, Announce.PERMISSION_REFUSED]


def test_structured_questions_that_cannot_be_read_are_asked_as_a_request(tmp_path: Path) -> None:
    view = FakeView(Decision(Choice.ALLOW))
    presenter, runner = _presenter(view, tmp_path)
    presenter.on_event(
        PermissionRequest("r1", "AskUserQuestion", "t", {"questions": 3}, "", "", "")
    )
    assert len(view.asked) == 1
    assert view.questions == []
    assert runner.answers == [("allow", "r1")]


def test_a_plan_is_refused_for_the_user_by_default_without_a_dialog(tmp_path: Path) -> None:
    view = FakeView(Decision(Choice.ALLOW))
    presenter, runner = _presenter(view, tmp_path)
    plan: dict[str, object] = {"plan": "# Plan\n\nStep one"}
    presenter.on_event(PermissionRequest("r1", "ExitPlanMode", "t", plan, "", "", ""))
    assert view.asked == []
    assert runner.answers == [("deny", PLAN_REFUSAL)]
    assert view.announces() == [Announce.PLAN_REFUSED]


def _in_plan_mode(presenter: RunPresenter) -> None:
    presenter._turn_agent = Agent(model="haiku", effort="low", permission_mode="plan")


def test_structured_questions_are_refused_in_the_plan_mode_without_a_dialog(
    tmp_path: Path,
) -> None:
    view = FakeView()
    view.question_answers = {"Which database?": ["SQLite"]}
    presenter, runner = _presenter(view, tmp_path)
    _in_plan_mode(presenter)
    presenter.on_event(PermissionRequest("r1", "AskUserQuestion", "t", QUESTION_INPUT, "", "", ""))
    assert view.questions == []
    assert view.asked == []
    assert runner.answered == []
    assert runner.answers == [("deny", PLAN_QUESTIONS_REFUSAL)]
    assert view.announces() == [Announce.PLAN_QUESTIONS_REFUSED]


def test_structured_questions_are_asked_outside_the_plan_mode_even_when_refusing(
    tmp_path: Path,
) -> None:
    view = FakeView()
    view.question_answers = {"Which database?": ["SQLite"]}
    presenter, runner = _presenter(view, tmp_path)  # the agent is not in the plan mode
    presenter.on_event(PermissionRequest("r1", "AskUserQuestion", "t", QUESTION_INPUT, "", "", ""))
    assert len(view.questions) == 1
    assert runner.answered == [{"Which database?": ["SQLite"]}]


def test_structured_questions_are_asked_in_the_plan_mode_when_not_refusing(
    tmp_path: Path,
) -> None:
    view = FakeView()
    view.question_answers = {"Which database?": ["SQLite"]}
    presenter, runner = _presenter(view, tmp_path)
    _in_plan_mode(presenter)
    presenter._settings.refuse_plan_mode_exit = False
    presenter.on_event(PermissionRequest("r1", "AskUserQuestion", "t", QUESTION_INPUT, "", "", ""))
    assert len(view.questions) == 1
    assert runner.answered == [{"Which database?": ["SQLite"]}]


def test_other_requests_are_still_asked_when_plans_are_refused(tmp_path: Path) -> None:
    view = FakeView(Decision(Choice.ALLOW))
    presenter, runner = _presenter(view, tmp_path)
    presenter.on_event(PermissionRequest("r1", "Bash", "t", {"command": "ls"}, "", "", ""))
    assert len(view.asked) == 1
    assert runner.answers == [("allow", "r1")]


def test_a_plan_is_announced_as_a_plan_and_can_be_approved(tmp_path: Path) -> None:
    view = FakeView(Decision(Choice.ALLOW))
    presenter, runner = _presenter(view, tmp_path)
    presenter._settings.refuse_plan_mode_exit = False
    plan: dict[str, object] = {"plan": "# Plan\n\nStep one"}
    presenter.on_event(PermissionRequest("r1", "ExitPlanMode", "t", plan, "", "", ""))
    assert Announce.PLAN_PROPOSED in view.announces()
    assert Announce.PERMISSION_ASKED not in view.announces()
    assert runner.answers == [("allow", "r1")]


def test_a_plan_can_be_refused_with_an_explanation(tmp_path: Path) -> None:
    view = FakeView(Decision(Choice.DENY, "Add the tests first"))
    presenter, runner = _presenter(view, tmp_path)
    presenter._settings.refuse_plan_mode_exit = False
    plan: dict[str, object] = {"plan": "Do it"}
    presenter.on_event(PermissionRequest("r1", "ExitPlanMode", "t", plan, "", "", ""))
    assert runner.answers == [("deny", "Add the tests first")]
