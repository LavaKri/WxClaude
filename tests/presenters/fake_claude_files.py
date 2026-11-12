"""The files of Claude Code in memory, for the tests of the presenters (see ``core/claude_files``).

The real files are tested once, in ``tests/core/``; here a test only says what Claude Code holds.
"""

from dataclasses import dataclass, field
from pathlib import Path

from wxclaude.core.claude.claude_projects import ClaudeProject, SessionInfo
from wxclaude.core.claude.claude_settings import FileGuard
from wxclaude.core.claude.cost_state import CostState
from wxclaude.core.claude.plans import Plan
from wxclaude.core.claude.session_reader import Session
from wxclaude.core.claude.tasks import Task, TaskList
from wxclaude.core.conversation.messages import Message, Role
from wxclaude.core.errors import (
    ClaudeSettingsError,
    PlanReadError,
    RunnerError,
    SessionReadError,
    TaskReadError,
)
from wxclaude.core.security.watch import ExternalChangeError


@dataclass(slots=True)
class FakeClaudeFiles:
    """Sessions by workspace, tasks and plans by conversation, the rules written."""

    sessions: dict[Path, list[SessionInfo]] = field(default_factory=dict)
    contents: dict[Path, Session] = field(default_factory=dict)  # by session file
    tasks: dict[str, list[Task]] = field(default_factory=dict)
    plans: dict[str, list[Plan]] = field(default_factory=dict)
    projects: list[ClaudeProject] = field(default_factory=list)
    rules: list[tuple[Path, str]] = field(default_factory=list)
    renamed: list[tuple[str, str]] = field(default_factory=list)  # (conversation, name)
    rename_error: str = ""  # when set, a rename fails with this message
    allow_error: str = ""  # when set, writing a rule fails with this message
    allow_external_change: ExternalChangeError | None = None  # when set, the write is refused
    guards: list[FileGuard | None] = field(default_factory=list)  # the guard of each write
    rename_restricted: list[bool] = field(default_factory=list)  # restricted, for each rename
    tasks_error: str = ""  # when set, reading the tasks fails with this message
    plans_error: str = ""  # when set, reading the plans fails with this message

    def add_session(
        self,
        workspace: Path,
        identifier: str,
        *prompts: str,
        title: str = "",
        total_cost: float | None = None,
        cost_states: list[CostState] | None = None,
    ) -> SessionInfo:
        """A conversation of ``workspace`` holding ``prompts``, the most recent one."""
        path = Path(f"{identifier}.jsonl")
        info = SessionInfo(identifier, path, title, float(len(self.contents)))
        session = Session(title=title, total_cost_usd=total_cost, cost_states=cost_states or [])
        session.messages = [
            Message(f"{identifier}-{i}", Role.USER, p) for i, p in enumerate(prompts)
        ]
        self.contents[path] = session
        self.sessions.setdefault(workspace, []).insert(0, info)
        return info

    def list_sessions(self, workspace: Path) -> list[SessionInfo]:
        return list(self.sessions.get(workspace, []))

    def find_session(self, conversation_id: str) -> Path | None:
        path = Path(f"{conversation_id}.jsonl")
        return path if path in self.contents else None

    def read_session(self, path: Path) -> Session:
        if path not in self.contents:
            raise SessionReadError(f"Cannot read {path}")
        return self.contents[path]

    def session_paths(self, conversation_id: str) -> list[Path]:
        path = Path(f"{conversation_id}.jsonl")
        return [path, Path(conversation_id)] if path in self.contents else []

    def load_tasks(self, conversation_id: str) -> TaskList:
        if self.tasks_error:
            raise TaskReadError(self.tasks_error)
        return TaskList(list(self.tasks.get(conversation_id, [])))

    def load_plans(self, conversation_id: str) -> list[Plan]:
        if self.plans_error:
            raise PlanReadError(self.plans_error)
        return list(self.plans.get(conversation_id, []))

    def list_projects(self) -> list[ClaudeProject]:
        return list(self.projects)

    def rename_session(
        self, conversation_id: str, name: str, workspace: Path, *, restricted: bool = False
    ) -> None:
        if self.rename_error:
            raise RunnerError(self.rename_error)
        self.renamed.append((conversation_id, name))
        self.rename_restricted.append(restricted)

    def allow_always(self, workspace: Path, rule: str, guard: FileGuard | None = None) -> None:
        if self.allow_error:
            raise ClaudeSettingsError(self.allow_error)
        if self.allow_external_change is not None:
            raise self.allow_external_change
        self.rules.append((workspace, rule))
        self.guards.append(guard)
