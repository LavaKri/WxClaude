"""The files of Claude Code that the presenters read or write, behind one contract.

``ClaudeFiles`` is what the presenters receive: the sessions, the tasks, the plans, the projects
and the "always allow" rules. ``DiskClaudeFiles`` is the real one (the functions of
``claude_projects``, ``session_reader``, ``tasks``, ``plans`` and ``claude_settings``, which know
where Claude Code keeps its files and test them on disk); the tests of the presenters use a fake
one in memory. WxClaude's own files (settings, workspace state) stay with ``Settings`` and
``WorkspaceState``.
"""

from pathlib import Path
from typing import Protocol

from wxclaude.core.claude import claude_projects, claude_settings, plans, session_reader, tasks
from wxclaude.core.claude.claude_projects import ClaudeProject, SessionInfo
from wxclaude.core.claude.plans import Plan
from wxclaude.core.claude.runner import ClaudeRunner
from wxclaude.core.claude.session_reader import Session
from wxclaude.core.claude.tasks import TaskList


class ClaudeFiles(Protocol):
    """What the presenters read and write of the files of Claude Code."""

    def list_sessions(self, workspace: Path) -> list[SessionInfo]:
        """The conversations of ``workspace``, the most recent first."""
        ...

    def find_session(self, conversation_id: str) -> Path | None:
        """The session file of a conversation; None if it has no history yet."""
        ...

    def read_session(self, path: Path) -> Session:
        """The session in ``path``; raises ``SessionReadError`` if it cannot be read."""
        ...

    def load_tasks(self, conversation_id: str) -> TaskList:
        """The task list of a conversation; raises ``TaskReadError`` if it cannot be read."""
        ...

    def load_plans(self, conversation_id: str) -> list[Plan]:
        """The plans of a conversation; raises ``PlanReadError`` if they cannot be read."""
        ...

    def list_projects(self) -> list[ClaudeProject]:
        """The folders Claude Code has worked in that still exist."""
        ...

    def rename_session(self, conversation_id: str, name: str, workspace: Path) -> None:
        """Give a conversation that has a session file a new name (the CLI's ``/rename``); raises
        ``RunnerError`` or ``ClaudeNotFoundError`` if it cannot."""
        ...

    def allow_always(self, workspace: Path, rule: str) -> None:
        """Write an allow rule in the personal settings file of ``workspace``; raises
        ``ClaudeSettingsError`` if it cannot."""
        ...


class DiskClaudeFiles:
    """The files of Claude Code on disk (``CLAUDE_CONFIG_DIR`` is honoured).

    A rename is not a write of ours: the CLI does it, through ``runner``.
    """

    def __init__(self, runner: ClaudeRunner | None = None) -> None:
        self._runner = runner or ClaudeRunner()

    def list_sessions(self, workspace: Path) -> list[SessionInfo]:
        return claude_projects.list_sessions(workspace)

    def find_session(self, conversation_id: str) -> Path | None:
        return claude_projects.find_session_file(conversation_id)

    def read_session(self, path: Path) -> Session:
        return session_reader.read_session(path)

    def load_tasks(self, conversation_id: str) -> TaskList:
        return tasks.load_tasks(conversation_id)

    def load_plans(self, conversation_id: str) -> list[Plan]:
        return plans.load_plans(conversation_id)

    def list_projects(self) -> list[ClaudeProject]:
        return claude_projects.list_projects()

    def rename_session(self, conversation_id: str, name: str, workspace: Path) -> None:
        self._runner.rename_session(conversation_id, name, workspace)

    def allow_always(self, workspace: Path, rule: str) -> None:
        claude_settings.allow_always(workspace, rule)
