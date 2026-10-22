"""The task list of a conversation, written by Claude Code in ``<config>/tasks/<session-id>/``.

Each task is a file ``<id>.json`` with ``id``, ``subject``, ``description``, ``status``
(``pending``, ``in_progress``, ``completed``) and ``blockedBy`` (see ``docs/claude-cli.md``).
WxClaude only reads them.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from wxclaude.core.claude_projects import claude_config_dir
from wxclaude.core.errors import TaskReadError
from wxclaude.i18n import N_, _

_STATUS_NAMES = {
    "pending": N_("pending"),
    "in_progress": N_("in progress"),
    "completed": N_("completed"),
}
_COMPLETED = "completed"
_IN_PROGRESS = "in_progress"
_UPDATE_TOOL = "TaskUpdate"  # {"taskId": "2", "status": "in_progress"}, seen with the real CLI


@dataclass(frozen=True, slots=True)
class Task:
    """A task of Claude; ``blocked_by`` are the identifiers of the tasks it waits for."""

    id: str
    subject: str
    description: str
    status: str
    blocked_by: tuple[str, ...] = ()


@dataclass(slots=True)
class TaskList:
    """The tasks of a conversation, in order, and the files that could not be read."""

    tasks: list[Task] = field(default_factory=list)
    unreadable: list[str] = field(default_factory=list)

    def line(self, task: Task) -> str:
        """How a task is listed: its number, subject and state, separated by commas.

        A task is said to be blocked only by the tasks that are not completed yet.
        """
        done = {other.id for other in self.tasks if other.status == _COMPLETED}
        parts = [task.id, task.subject, status_name(task.status)]
        waiting = [identifier for identifier in task.blocked_by if identifier not in done]
        if waiting:
            parts.append(_("blocked by {tasks}").format(tasks=" ".join(waiting)))
        return ", ".join(part for part in parts if part)


@dataclass(frozen=True, slots=True)
class Step:
    """The task Claude works on: its place in the list (``number`` of ``total``) and its subject."""

    number: int
    total: int
    subject: str


def started_task_id(tool_name: str, tool_input: dict[str, object]) -> str | None:
    """The task a tool call puts in progress (``TaskUpdate`` with that status), else None."""
    if tool_name != _UPDATE_TOOL or tool_input.get("status") != _IN_PROGRESS:
        return None
    identifier = tool_input.get("taskId")
    return str(identifier) if isinstance(identifier, str | int) else None


def step_of(task_id: str, tasks: TaskList) -> Step | None:
    """The step the task ``task_id`` is in the list; None if the list does not hold it."""
    for index, task in enumerate(tasks.tasks):
        if task.id == task_id:
            return Step(index + 1, len(tasks.tasks), task.subject)
    return None


def status_name(status: str) -> str:
    """The name of a task status, as shown (an unknown status is shown as it is)."""
    return _(_STATUS_NAMES[status]) if status in _STATUS_NAMES else status


def _sort_key(task: Task) -> tuple[int, int, str]:
    return (0, int(task.id), "") if task.id.isdecimal() else (1, 0, task.id)


def _strings(value: object) -> tuple[str, ...]:
    return tuple(str(item) for item in value) if isinstance(value, list) else ()


def _read_task(path: Path) -> Task | None:
    """The task in ``path``; None if it is not a task (invalid JSON, not an object)."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return None
    if not isinstance(raw, dict):
        return None
    return Task(
        id=str(raw.get("id") or path.stem),
        subject=str(raw.get("subject") or ""),
        description=str(raw.get("description") or ""),
        status=str(raw.get("status") or ""),
        blocked_by=_strings(raw.get("blockedBy")),
    )


def load_tasks(session_id: str, config_dir: Path | None = None) -> TaskList:
    """The tasks of the session ``session_id`` (none if Claude never made a list).

    A file that is not a readable task is left out and named in ``unreadable``. Raises
    ``TaskReadError`` if the folder itself cannot be read.
    """
    folder = (config_dir or claude_config_dir()) / "tasks" / session_id
    result = TaskList()
    try:
        if not folder.is_dir():
            return result
        files = sorted(folder.glob("*.json"))
    except OSError as error:
        raise TaskReadError(f"Cannot read the tasks in {folder}: {error}") from error
    for path in files:
        task = _read_task(path)
        if task is None:
            result.unreadable.append(path.name)
        else:
            result.tasks.append(task)
    result.tasks.sort(key=_sort_key)
    return result
