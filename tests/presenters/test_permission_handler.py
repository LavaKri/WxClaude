"""The questions of Claude during a message, with a fake view and a fake runner.

The course of a permission (asked, allowed, denied, always allowed, expired) is also tested through
``RunPresenter`` in ``test_run_presenter.py``; here are the paths where the CLI cannot be answered.
"""

from collections.abc import Callable
from pathlib import Path

import pytest
from fake_claude_files import FakeClaudeFiles

from wxclaude.core.claude.events import PermissionExpired, PermissionRequest
from wxclaude.core.claude.permissions import Choice, Decision
from wxclaude.core.claude.questions import Question
from wxclaude.core.claude.runner import ClaudeRunner
from wxclaude.core.claude.usage import UsageTracker
from wxclaude.core.config.settings import Settings
from wxclaude.core.errors import RunnerError
from wxclaude.core.speech.announcements import Announce
from wxclaude.presenters.permission_handler import PermissionHandler, PermissionLinks
from wxclaude.presenters.shared import Shared
from wxclaude.presenters.stats_recorder import StatsRecorder

pytestmark = pytest.mark.unit

GONE = "Claude is not waiting for an answer."
QUESTIONS: dict[str, object] = {
    "questions": [
        {
            "question": "Which database?",
            "header": "Database",
            "options": [{"label": "SQLite", "description": "A file"}],
        }
    ]
}


class FakeView:
    """Answers the questions with what the test sets, and records the rest."""

    def __init__(self) -> None:
        self.decision = Decision(Choice.ALLOW)
        self.answers: dict[str, list[str]] | None = {"Which database?": ["SQLite"]}
        self.said: list[Announce] = []
        self.errors: list[str] = []
        self.closed: list[str] = []
        self.while_open: Callable[[], None] = lambda: None  # what happens while one is open

    def ask_permission(self, request: PermissionRequest, wait_text: str = "") -> Decision:
        self.while_open()
        return self.decision

    def ask_questions(self, questions: list[Question]) -> dict[str, list[str]] | None:
        self.while_open()
        return self.answers

    def close_permission(self, request_id: str) -> None:
        self.closed.append(request_id)

    def say(self, announce: Announce, **values: object) -> None:
        self.said.append(announce)

    def show_error(self, message: str) -> None:
        self.errors.append(message)


class FakeRunner(ClaudeRunner):
    """Records the answers; every answer fails with ``RunnerError`` when ``gone`` is set."""

    def __init__(self) -> None:
        super().__init__()
        self.gone = False
        self.answers: list[str] = []

    def _record(self, what: str) -> None:
        if self.gone:
            raise RunnerError(GONE)
        self.answers.append(what)

    def allow(self, request: PermissionRequest) -> None:
        self._record("allow")

    def deny(self, request: PermissionRequest, message: str) -> None:
        self._record("deny")

    def answer_questions(self, request: PermissionRequest, answers: dict[str, list[str]]) -> None:
        self._record("answers")


class Setup:
    """A handler with its fakes; the workspace and what the presenter says can be inspected."""

    def __init__(self, workspace: Path | None) -> None:
        self.view = FakeView()
        self.runner = FakeRunner()
        self.files = FakeClaudeFiles()
        self.settings = Settings.load(None)
        self.workspace = workspace
        self.said: list[Announce] = []
        shared = Shared(self.settings, UsageTracker(), self.files)
        links = PermissionLinks(
            say=lambda announce, **values: self.said.append(announce),
            turn_mode=lambda: None,
            workspace=lambda: self.workspace,
        )
        self.handler = PermissionHandler(
            self.view,
            self.runner,
            shared,
            StatsRecorder(lambda: None, lambda message: None),
            links,
        )


def _request(
    request_id: str = "r1",
    tool: str = "Bash",
    rule: str = "",
    tool_input: dict[str, object] | None = None,
) -> PermissionRequest:
    return PermissionRequest(request_id, tool, "t", tool_input or {}, "", "", rule)


def test_a_tool_that_cannot_be_allowed_is_reported_and_not_announced(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    setup.runner.gone = True
    setup.handler.request(_request())
    assert setup.view.errors == [f"Claude could not be answered.\n{GONE}"]
    assert Announce.PERMISSION_GRANTED not in setup.view.said


def test_a_tool_that_cannot_be_denied_is_reported_and_not_announced(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    setup.view.decision = Decision(Choice.DENY)
    setup.runner.gone = True
    setup.handler.request(_request())
    assert setup.view.errors == [f"Claude could not be answered.\n{GONE}"]
    assert Announce.PERMISSION_REFUSED not in setup.view.said


def test_a_plan_that_cannot_be_refused_is_reported_and_the_refusal_is_not_announced(
    tmp_path: Path,
) -> None:
    setup = Setup(tmp_path)
    setup.runner.gone = True
    setup.handler.request(_request(tool="ExitPlanMode", tool_input={"plan": "# Plan"}))
    assert setup.view.errors == [f"Claude could not be answered.\n{GONE}"]
    assert setup.said == []


def test_a_plan_that_is_refused_says_so(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    setup.handler.request(_request(tool="ExitPlanMode", tool_input={"plan": "# Plan"}))
    assert setup.runner.answers == ["deny"]
    assert setup.said == [Announce.PLAN_REFUSED]


def test_answers_that_cannot_be_given_back_are_reported(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    setup.runner.gone = True
    setup.handler.request(_request(tool="AskUserQuestion", tool_input=QUESTIONS))
    assert setup.view.errors == [f"Claude could not be answered.\n{GONE}"]
    assert Announce.QUESTION_ANSWERED not in setup.said


def test_questions_that_expire_while_open_are_not_answered(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    request = _request(tool="AskUserQuestion", tool_input=QUESTIONS)
    setup.view.while_open = lambda: setup.handler.expired(
        PermissionExpired("r1", "AskUserQuestion")
    )
    setup.handler.request(request)
    assert setup.runner.answers == []
    assert setup.view.closed == ["r1"]
    assert setup.said == [Announce.QUESTION_ASKED, Announce.PERMISSION_EXPIRED]


def test_always_allow_without_a_workspace_is_kept_for_the_message_but_not_written() -> None:
    setup = Setup(None)
    setup.view.decision = Decision(Choice.ALLOW_ALWAYS)
    setup.handler.request(_request(rule="Bash(touch x)"))
    setup.handler.request(_request("r2", rule="Bash(touch x)"))
    assert setup.runner.answers == ["allow", "allow"]
    assert setup.files.rules == []
    assert setup.view.errors == []


def test_a_new_message_forgets_what_was_always_allowed(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    setup.view.decision = Decision(Choice.ALLOW_ALWAYS)
    setup.handler.request(_request(rule="Bash(touch x)"))
    setup.view.decision = Decision(Choice.DENY)
    setup.handler.request(_request("r2", rule="Bash(touch x)"))  # still allowed: not asked
    assert setup.runner.answers == ["allow", "allow"]
    setup.handler.start_message()
    setup.handler.request(_request("r3", rule="Bash(touch x)"))  # asked again, and denied
    assert setup.runner.answers == ["allow", "allow", "deny"]
