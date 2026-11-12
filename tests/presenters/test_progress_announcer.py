"""What is said while Claude answers, with a fake view: no repeat, notices, the step of the tasks.

The same things are also tested through ``RunPresenter`` (``test_run_presenter*.py``).
"""

import pytest
from fake_claude_files import FakeClaudeFiles

from wxclaude.core.claude.events import McpServer, SessionInit, ToolUsed
from wxclaude.core.claude.progress import Progress
from wxclaude.core.claude.tasks import Task
from wxclaude.core.speech.announcements import Announce
from wxclaude.presenters.progress_announcer import ProgressAnnouncer, ProgressLinks

pytestmark = pytest.mark.unit

THINKING = Progress(Announce.CLAUDE_THINKING)
TOOL = Progress(Announce.CLAUDE_USING_TOOL, {"tool": "Read"})
IN_PROGRESS = ToolUsed("t", "TaskUpdate", {"taskId": "1", "status": "in_progress"})


class FakeView:
    def __init__(self) -> None:
        self.said: list[tuple[Announce, dict[str, object]]] = []
        self.steps: list[str] = []
        self.errors: list[str] = []

    def say(self, announce: Announce, **values: object) -> None:
        self.said.append((announce, values))

    def show_step(self, text: str) -> None:
        self.steps.append(text)

    def show_error(self, message: str) -> None:
        self.errors.append(message)

    def announces(self) -> list[Announce]:
        return [announce for announce, _values in self.said]


def _announcer(files: FakeClaudeFiles | None = None) -> tuple[ProgressAnnouncer, FakeView]:
    view = FakeView()

    def say(announce: Announce, **values: object) -> None:
        view.say(announce, name="Claude", **values)  # as the presenter does: naming who answers

    links = ProgressLinks(say, lambda: "Claude", lambda: "c1")
    return ProgressAnnouncer(view, files or FakeClaudeFiles(), links), view


def test_the_same_progress_twice_in_a_row_is_said_once() -> None:
    announcer, view = _announcer()
    announcer.show(THINKING)
    announcer.show(THINKING)
    assert view.announces() == [Announce.CLAUDE_THINKING]


def test_another_progress_is_said_and_the_first_can_be_said_again_after_it() -> None:
    announcer, view = _announcer()
    announcer.show(THINKING)
    announcer.show(TOOL)
    announcer.show(THINKING)
    assert view.announces() == [
        Announce.CLAUDE_THINKING,
        Announce.CLAUDE_USING_TOOL,
        Announce.CLAUDE_THINKING,
    ]


def test_a_new_message_says_its_first_progress_even_if_the_last_one_was_the_same() -> None:
    announcer, view = _announcer()
    announcer.show(THINKING)
    announcer.reset()
    announcer.show(THINKING)
    assert view.announces() == [Announce.CLAUDE_THINKING] * 2


def test_an_announcement_is_made_even_if_it_is_the_same_and_lets_the_next_progress_be_said() -> (
    None
):
    announcer, view = _announcer()
    announcer.show(THINKING)
    announcer.announce(THINKING)
    announcer.show(THINKING)
    assert view.announces() == [Announce.CLAUDE_THINKING] * 3


def test_a_server_that_failed_is_told_once_and_a_forced_mode_is_explained() -> None:
    announcer, view = _announcer()
    init = SessionInit("s", "m", "default", (McpServer("ollama", "failed"),))
    announcer.announce_start(init, "plan", masked=True)
    announcer.announce_start(init, "plan", masked=True)
    assert view.announces() == [
        Announce.MODE_FORCED_MANUAL,
        Announce.MCP_SERVER_FAILED,
        Announce.MODE_FORCED_MANUAL,
    ]


def test_a_mode_that_was_applied_says_nothing() -> None:
    announcer, view = _announcer()
    announcer.announce_start(SessionInit("s", "m", "plan"), "plan", masked=False)
    assert view.said == []


def test_a_task_put_in_progress_is_a_step_in_the_status_bar_and_is_said() -> None:
    files = FakeClaudeFiles(tasks={"c1": [Task("1", "Alpha", "", "pending")]})
    announcer, view = _announcer(files)
    assert announcer.show_step(IN_PROGRESS)
    assert view.steps == ["Step 1 of 1: Alpha"]
    assert view.said == [(Announce.STEP_STARTED, {"number": 1, "total": 1, "subject": "Alpha"})]


def test_what_comes_after_a_step_is_said_again() -> None:
    files = FakeClaudeFiles(tasks={"c1": [Task("1", "Alpha", "", "pending")]})
    announcer, view = _announcer(files)
    announcer.show(THINKING)
    announcer.show_step(IN_PROGRESS)
    announcer.show(THINKING)
    assert view.announces() == [
        Announce.CLAUDE_THINKING,
        Announce.STEP_STARTED,
        Announce.CLAUDE_THINKING,
    ]


def test_a_call_that_is_not_a_task_put_in_progress_is_normal_progress() -> None:
    announcer, view = _announcer()
    assert not announcer.show_step(ToolUsed("t", "Read", {}))
    assert view.said == []
    assert view.steps == []


def test_a_task_that_is_not_in_the_list_is_normal_progress() -> None:
    announcer, view = _announcer(FakeClaudeFiles(tasks={"c1": []}))
    assert not announcer.show_step(IN_PROGRESS)
    assert view.said == []
    assert view.steps == []


def test_a_task_list_that_cannot_be_read_is_reported_and_the_call_is_normal_progress() -> None:
    announcer, view = _announcer(FakeClaudeFiles(tasks_error="Cannot read the tasks file"))
    assert not announcer.show_step(IN_PROGRESS)
    assert view.errors == ["Cannot read the tasks.\nCannot read the tasks file"]
