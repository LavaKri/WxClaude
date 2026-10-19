"""The projects Claude Code knows: the folders it has already worked in.

Claude Code keeps one sub-folder per working folder under ``<config>/projects``. The name of that
sub-folder is an encoding of the path that cannot always be decoded, so the real path is read from
the ``cwd`` field of the session files it contains.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path

from wxclaude.core.conversations import is_conversation_id

_LINES_TO_READ = 200  # the working folder is in the first lines of a session file


@dataclass(frozen=True, slots=True)
class ClaudeProject:
    """A working folder known to Claude Code, and when a session of it was last written."""

    folder: Path
    last_used: float


def claude_projects_dir() -> Path:
    """Where Claude Code keeps its projects (``CLAUDE_CONFIG_DIR`` is honoured)."""
    config = os.environ.get("CLAUDE_CONFIG_DIR")
    return (Path(config) if config else Path.home() / ".claude") / "projects"


def _working_folder(session_file: Path) -> Path | None:
    """The ``cwd`` recorded in a session file, None if there is none."""
    try:
        with session_file.open(encoding="utf-8", errors="replace") as lines:
            for number, line in enumerate(lines):
                if number >= _LINES_TO_READ:
                    break
                if '"cwd"' not in line:
                    continue
                try:
                    cwd = json.loads(line).get("cwd")
                except json.JSONDecodeError:
                    continue
                if isinstance(cwd, str) and cwd:
                    return Path(cwd)
    except OSError:
        return None
    return None


@dataclass(frozen=True, slots=True)
class SessionInfo:
    """A conversation found on disk: its identifier, file, title ('' if none) and last write."""

    id: str
    path: Path
    title: str
    last_used: float


def _session_title(session_file: Path) -> str:
    """The title of a session file: the last rename, else the last generated title."""
    custom = generated = ""
    try:
        with session_file.open(encoding="utf-8", errors="replace") as lines:
            for line in lines:
                if '"custom-title"' in line:
                    key, kind = "customTitle", "custom"
                elif '"ai-title"' in line:
                    key, kind = "aiTitle", "ai"
                else:
                    continue
                try:
                    title = json.loads(line).get(key)
                except json.JSONDecodeError:
                    continue
                if isinstance(title, str):
                    if kind == "custom":
                        custom = title
                    else:
                        generated = title
    except OSError:
        return ""
    return custom or generated


def list_sessions(workspace: Path, projects_dir: Path | None = None) -> list[SessionInfo]:
    """The conversations Claude Code holds for ``workspace``, the most recent first."""
    root = projects_dir or claude_projects_dir()
    wanted = str(workspace).lower()
    found: list[SessionInfo] = []
    try:
        entries = [entry for entry in root.iterdir() if entry.is_dir()]
    except OSError:
        return []
    for entry in entries:
        sessions = sorted(entry.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not sessions:
            continue
        folder = _working_folder(sessions[0])
        if folder is None or str(folder).lower() != wanted:
            continue
        found.extend(
            SessionInfo(file.stem, file, _session_title(file), file.stat().st_mtime)
            for file in sessions
            if is_conversation_id(file.stem)
        )
    return sorted(found, key=lambda session: session.last_used, reverse=True)


def list_projects(projects_dir: Path | None = None) -> list[ClaudeProject]:
    """The projects whose folder still exists, the most recently used first."""
    root = projects_dir or claude_projects_dir()
    found: dict[str, ClaudeProject] = {}
    try:
        entries = [entry for entry in root.iterdir() if entry.is_dir()]
    except OSError:
        return []
    for entry in entries:
        sessions = sorted(entry.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not sessions:
            continue
        folder = _working_folder(sessions[0])
        if folder is None or not folder.is_dir():
            continue
        project = ClaudeProject(folder, sessions[0].stat().st_mtime)
        key = str(folder).lower()
        if key not in found or project.last_used > found[key].last_used:
            found[key] = project
    return sorted(found.values(), key=lambda project: project.last_used, reverse=True)
