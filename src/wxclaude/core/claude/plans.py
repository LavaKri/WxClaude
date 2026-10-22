"""The plans of a conversation: the files Claude Code writes in ``<config>/plans/`` in plan mode.

A plan is a ``Write`` of the session to a file of that folder (``docs/claude-cli.md``, "Permission
channels": it is the same with the stdio protocol and with the HTTP hook). The session file names
the plans; the text is read from the plan file, which Claude may have edited since, or, if the
file is gone, taken from what the session wrote. WxClaude only reads them.
"""

from dataclasses import dataclass
from pathlib import Path

from wxclaude.core.claude.claude_projects import claude_config_dir, find_session_file
from wxclaude.core.claude.session_reader import Session, read_session
from wxclaude.core.conversation.messages import ToolUse
from wxclaude.core.errors import PlanReadError, SessionReadError
from wxclaude.i18n import _


@dataclass(frozen=True, slots=True)
class Plan:
    """A plan: its file, its text, and whether the text was read from the file."""

    path: Path
    text: str
    in_file: bool

    @property
    def line(self) -> str:
        """How a plan is listed: the name of its file, said when the file is gone."""
        if self.in_file:
            return self.path.name
        return _("{name}, file missing, text from the session").format(name=self.path.name)


def _plan_path(tool: ToolUse, folder: Path) -> Path | None:
    """The plan file a ``Write`` creates, None if the call writes anything else."""
    if tool.name != "Write":
        return None
    file_path = tool.input.get("file_path")
    if not isinstance(file_path, str):
        return None
    path = Path(file_path)
    return path if path.is_relative_to(folder) else None


def plans_of_session(session: Session, config_dir: Path | None = None) -> list[Plan]:
    """The plans written in ``session``, oldest first (a plan written again keeps its place)."""
    folder = (config_dir or claude_config_dir()) / "plans"
    written: dict[Path, str] = {}
    for message in session.messages:
        for tool in message.tools:
            path = _plan_path(tool, folder)
            if path is not None:
                written[path] = str(tool.input.get("content", ""))
    plans: list[Plan] = []
    for path, content in written.items():
        try:
            plans.append(Plan(path, path.read_text(encoding="utf-8"), in_file=True))
        except OSError:
            plans.append(Plan(path, content, in_file=False))  # the file is gone or unreadable
    return plans


def load_plans(
    session_id: str, config_dir: Path | None = None, projects_dir: Path | None = None
) -> list[Plan]:
    """The plans of the conversation ``session_id`` (none if it has no history or no plan).

    Raises ``PlanReadError`` if its session file cannot be read.
    """
    session_file = find_session_file(session_id, projects_dir)
    if session_file is None:
        return []
    try:
        session = read_session(session_file)
    except SessionReadError as error:
        raise PlanReadError(f"Cannot read the plans of {session_file}: {error}") from error
    return plans_of_session(session, config_dir)
