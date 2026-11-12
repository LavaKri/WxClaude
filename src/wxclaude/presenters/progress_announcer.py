"""What is said while Claude answers: the progress (thinking, a tool, a file read…), the notices at
the start of the CLI, and the step of the task list that Claude puts in progress.

Taken out of ``RunPresenter``. The same text twice in a row is said once; what comes after a notice
or a step is said again, because it is about something else.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from wxclaude.core.claude.claude_files import ClaudeFiles
from wxclaude.core.claude.events import SessionInit, ToolUsed
from wxclaude.core.claude.progress import Progress, mcp_progress, mode_progress
from wxclaude.core.claude.tasks import started_task_id, step_of
from wxclaude.core.errors import TaskReadError
from wxclaude.core.speech.announcements import Announce, AnnouncementCenter
from wxclaude.i18n import _


class ProgressView(Protocol):
    """What the announcer asks of the interface (``RunView`` gives it)."""

    def say(self, announce: Announce, **values: object) -> None:
        """Announce, where the category of ``announce`` says."""
        ...

    def show_step(self, text: str) -> None:
        """The step field of the status bar ('' when there is none)."""
        ...

    def show_error(self, message: str) -> None:
        """Tell the user that something failed."""
        ...


@dataclass(frozen=True, slots=True)
class ProgressLinks:
    """What the announcer asks of the presenter: ``say`` announces naming who answers (Claude, or
    the provider), ``speaker`` is that name, and ``conversation_id`` the conversation being
    answered (where the task list is)."""

    say: Callable[..., None]
    speaker: Callable[[], str]
    conversation_id: Callable[[], str]


class ProgressAnnouncer:
    """Says the progress of a message, without repeating itself."""

    def __init__(self, view: ProgressView, files: ClaudeFiles, links: ProgressLinks) -> None:
        self._view = view
        self._files = files
        self._links = links
        self._last_progress = ""  # the last progress shown, not repeated
        self._mcp_reported: dict[str, str] = {}  # the MCP servers already told about, and state

    def reset(self) -> None:
        """A new message starts: its first progress is said, whatever the last one was."""
        self._last_progress = ""

    def show(self, progress: Progress) -> None:
        """Progress goes where the category of its announcement says; the same text twice in a
        row is said once."""
        text = AnnouncementCenter.text(
            progress.announce, name=self._links.speaker(), **progress.values
        )
        if text == self._last_progress:
            return
        self._last_progress = text
        self._links.say(progress.announce, **progress.values)

    def announce(self, progress: Progress) -> None:
        """Say ``progress`` now, even if it is the same as the last one, and let the progress
        that follows be said again (it is about what comes after)."""
        self._links.say(progress.announce, **progress.values)
        self._last_progress = ""

    def announce_start(self, init: SessionInit, mode: str, *, masked: bool) -> None:
        """What the start of the CLI shows that the user should know: a permission mode that was
        not applied (``mode`` is the one it was given), an MCP server that did not start."""
        mode_notice = mode_progress(mode, init.permission_mode, masked=masked)
        notices = [mode_notice] if mode_notice is not None else []
        notices += mcp_progress(init.mcp_servers, self._mcp_reported)
        for notice in notices:
            self.announce(notice)

    def show_step(self, tool: ToolUsed) -> bool:
        """Claude puts a task of its list in progress: say which step, and keep it in the status
        bar. False when the call is not that (or the task is not in the list): normal progress."""
        task_id = started_task_id(tool.name, tool.input)
        if task_id is None:
            return False
        try:
            tasks = self._files.load_tasks(self._links.conversation_id())
        except TaskReadError as error:
            self._view.show_error(_("Cannot read the tasks.\n{error}").format(error=error))
            return False
        step = step_of(task_id, tasks)
        if step is None:
            return False
        values = {"number": step.number, "total": step.total, "subject": step.subject}
        self._view.show_step(AnnouncementCenter.text(Announce.STEP_STARTED, **values))
        self._view.say(Announce.STEP_STARTED, **values)
        self._last_progress = ""  # what comes next is said again, it is about another step
        return True
