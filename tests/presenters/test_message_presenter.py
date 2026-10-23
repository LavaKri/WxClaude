"""The presenter of the messages and their details, with a fake view: no wx, no window."""

from collections.abc import Sequence
from pathlib import Path

import pytest
from fake_claude_files import FakeClaudeFiles

from wxclaude.core.claude.plans import Plan
from wxclaude.core.claude.tasks import Task, TaskList
from wxclaude.core.claude.usage import UsageTracker
from wxclaude.core.conversation.details import DetailAction, Link, Table
from wxclaude.core.conversation.messages import Message, Role, ToolUse
from wxclaude.presenters.message_presenter import LinkAction, LinkChoice, MessagePresenter

pytestmark = pytest.mark.unit

CONVERSATION = "d278c1fc-1d73-4c16-a899-5bdb1831fe5c"
ANSWER = Message(
    "m",
    Role.ASSISTANT,
    "| Name | Size |\n|---|---|\n| a.txt | 3 |\n\n[one](https://1.test) and [two](ftp://x.test/f)",
    model="m",
    tools=[ToolUse("t", "Read", {"file_path": "a.py"})],
)


class FakeView:
    """Records what is shown; answers the table and the links with what the test set."""

    def __init__(self) -> None:
        self.copy_table = False
        self.link: LinkChoice | None = None
        self.clipboard_works = True
        self.browser_works = True
        self.copied: list[str] = []
        self.opened: list[str] = []
        self.shown: list[object] = []
        self.errors: list[str] = []

    def exchange_of(self, message: Message) -> str:
        return f"exchange of {message.id}"

    def show_tools(self, tools: Sequence[ToolUse]) -> None:
        self.shown.append(list(tools))

    def ask_table(self, table: Table) -> bool:
        self.shown.append(table)
        return self.copy_table

    def ask_link(self, links: Sequence[Link], selected: int) -> LinkChoice | None:
        self.shown.append((list(links), selected))
        return self.link

    def show_tasks(self, tasks: TaskList) -> None:
        self.shown.append(tasks)

    def show_plans(self, plans: list[Plan]) -> None:
        self.shown.append(plans)

    def show_usage(self, lines: list[str]) -> None:
        self.shown.append(lines)

    def set_clipboard(self, text: str) -> bool:
        self.copied.append(text)
        return self.clipboard_works

    def open_url(self, url: str) -> bool:
        self.opened.append(url)
        return self.browser_works

    def show_error(self, message: str) -> None:
        self.errors.append(message)


@pytest.fixture
def view() -> FakeView:
    return FakeView()


@pytest.fixture
def files() -> FakeClaudeFiles:
    return FakeClaudeFiles()


@pytest.fixture
def presenter(view: FakeView, files: FakeClaudeFiles) -> MessagePresenter:
    return MessagePresenter(view, lambda: CONVERSATION, UsageTracker(), files)


def test_a_message_and_its_exchange_are_copied(view: FakeView, presenter: MessagePresenter) -> None:
    presenter.act(DetailAction.COPY_MESSAGE, ANSWER, -1)
    presenter.act(DetailAction.COPY_EXCHANGE, ANSWER, -1)
    assert view.copied == [ANSWER.text, "exchange of m"]


def test_a_clipboard_that_cannot_be_used_is_reported(
    view: FakeView, presenter: MessagePresenter
) -> None:
    view.clipboard_works = False
    presenter.act(DetailAction.COPY_MESSAGE, ANSWER, -1)
    assert view.errors == ["The clipboard cannot be used."]


def test_the_tools_and_the_table_are_shown_and_the_table_copied_on_request(
    view: FakeView, presenter: MessagePresenter
) -> None:
    presenter.act(DetailAction.TOOLS, ANSWER, -1)
    assert view.shown == [ANSWER.tools]
    view.copy_table = True
    presenter.act(DetailAction.TABLE, ANSWER, 2)
    assert view.copied == ["| Name | Size |\n|---|---|\n| a.txt | 3 |"]
    presenter.act(DetailAction.TABLE, ANSWER, 4)  # not a line of the table: nothing
    assert len(view.shown) == 2


def test_a_web_link_is_opened_and_another_kind_refused(
    view: FakeView, presenter: MessagePresenter
) -> None:
    view.link = LinkChoice(LinkAction.OPEN, 0)
    presenter.act(DetailAction.LINKS, ANSWER, 4)
    view.link = LinkChoice(LinkAction.OPEN, 1)
    presenter.act(DetailAction.LINKS, ANSWER, 4)
    assert view.opened == ["https://1.test"]
    assert view.errors == ["This kind of address is not opened from here: ftp://x.test/f"]
    view.link = LinkChoice(LinkAction.COPY, 1)
    presenter.act(DetailAction.LINKS, ANSWER, 4)
    assert view.copied == ["ftp://x.test/f"]


def test_a_browser_that_refuses_is_reported(view: FakeView, presenter: MessagePresenter) -> None:
    view.browser_works = False
    view.link = LinkChoice(LinkAction.OPEN, 0)
    presenter.act(DetailAction.LINKS, ANSWER, 4)
    assert view.errors == ["The address https://1.test cannot be opened."]


def test_the_tasks_of_the_conversation_are_read_and_shown(
    view: FakeView, presenter: MessagePresenter, files: FakeClaudeFiles
) -> None:
    files.tasks[CONVERSATION] = [Task("1", "Alpha", "", "pending")]
    presenter.show_tasks()
    (tasks,) = view.shown
    assert isinstance(tasks, TaskList)
    assert [task.subject for task in tasks.tasks] == ["Alpha"]


def test_the_plans_of_the_conversation_are_read_and_shown(
    view: FakeView, presenter: MessagePresenter, files: FakeClaudeFiles, tmp_path: Path
) -> None:
    plan = Plan(tmp_path / "calm-fox.md", "# Plan", in_file=True)
    files.plans[CONVERSATION] = [plan]
    presenter.show_plans()
    assert view.shown == [[plan]]


def test_tasks_or_plans_that_cannot_be_read_are_reported(
    view: FakeView, presenter: MessagePresenter, files: FakeClaudeFiles
) -> None:
    files.tasks_error = "broken task folder"
    files.plans_error = "broken session file"
    presenter.show_tasks()
    presenter.show_plans()
    assert view.shown == []
    assert view.errors == [
        "Cannot read the tasks.\nbroken task folder",
        "Cannot read the plans.\nbroken session file",
    ]


def test_the_usage_is_shown_even_before_any_answer(
    view: FakeView, presenter: MessagePresenter
) -> None:
    presenter.show_usage()
    (lines,) = view.shown
    assert isinstance(lines, list)
    assert lines[0].startswith("No subscription usage information yet")
