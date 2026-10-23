"""The files of Claude Code in memory, for the tests of the presenters (see ``core/claude_files``).

The real files are tested once, in ``tests/core/``; here a test only says what Claude Code holds.
"""

from dataclasses import dataclass, field
from pathlib import Path

from wxclaude.core.claude.claude_projects import ClaudeProject, SessionInfo
from wxclaude.core.claude.plans import Plan
from wxclaude.core.claude.session_reader import Session
from wxclaude.core.claude.tasks import Task, TaskList
from wxclaude.core.conversation.messages import Message, Role
from wxclaude.core.errors import RunnerError, SessionReadError


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

    def add_session(
        self, workspace: Path, identifier: str, *prompts: str, title: str = ""
    ) -> SessionInfo:
        """A conversation of ``workspace`` holding ``prompts``, the most recent one."""
        path = Path(f"{identifier}.jsonl")
        info = SessionInfo(identifier, path, title, float(len(self.contents)))
        session = Session(title=title)
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

    def load_tasks(self, conversation_id: str) -> TaskList:
        return TaskList(list(self.tasks.get(conversation_id, [])))

    def load_plans(self, conversation_id: str) -> list[Plan]:
        return list(self.plans.get(conversation_id, []))

    def list_projects(self) -> list[ClaudeProject]:
        return list(self.projects)

    def rename_session(self, conversation_id: str, name: str, workspace: Path) -> None:
        if self.rename_error:
            raise RunnerError(self.rename_error)
        self.renamed.append((conversation_id, name))

    def allow_always(self, workspace: Path, rule: str) -> None:
        self.rules.append((workspace, rule))
