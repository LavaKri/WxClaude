"""The projects Claude Code knows: the folders it has already worked in.

Claude Code keeps one sub-folder per working folder under ``<config>/projects``. The name of that
sub-folder is an encoding of the path that cannot always be decoded, so the real path is read from
the ``cwd`` field of the session files it contains.
"""

import json
import os
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from wxclaude.core.conversations import is_conversation_id

_LINES_TO_READ = 200  # the working folder is in the first lines of a session file
_CANDIDATE_LINES = 20  # lines kept to find the time of the last message


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
    """A conversation found on disk: its identifier, file, title ('' if none) and last message."""

    id: str
    path: Path
    title: str
    last_used: float  # when the last prompt or answer was written (the file date if unknown)


def _message_time(line: str) -> float | None:
    """The time of the prompt or answer written on ``line``, None if it is neither."""
    try:
        entry = json.loads(line)
        if entry.get("type") not in ("user", "assistant") or entry.get("isSidechain"):
            return None
        return datetime.fromisoformat(entry["timestamp"]).timestamp()
    except json.JSONDecodeError, AttributeError, KeyError, TypeError, ValueError:
        return None


def _scan_session(session_file: Path) -> tuple[str, float]:
    """The title of a session (last rename, else last generated) and the time of its last message.

    Renames and title entries are written again and again, so the date of the file says little
    about the last exchange.
    """
    custom = generated = ""
    candidates: deque[str] = deque(maxlen=_CANDIDATE_LINES)  # the last lines that may be messages
    try:
        with session_file.open(encoding="utf-8", errors="replace") as lines:
            for line in lines:
                if '"custom-title"' in line or '"ai-title"' in line:
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(entry.get("customTitle"), str):
                        custom = entry["customTitle"]
                    elif isinstance(entry.get("aiTitle"), str):
                        generated = entry["aiTitle"]
                elif '"timestamp"' in line and '"message"' in line:
                    candidates.append(line)
        fallback = session_file.stat().st_mtime
    except OSError:
        return "", 0.0
    times = (_message_time(line) for line in reversed(candidates))
    return custom or generated, next((t for t in times if t is not None), fallback)


def find_session_file(session_id: str, projects_dir: Path | None = None) -> Path | None:
    """The file of the session ``session_id``, None if Claude Code holds no such session."""
    root = projects_dir or claude_projects_dir()
    try:
        for entry in root.iterdir():
            candidate = entry / f"{session_id}.jsonl"
            if candidate.is_file():
                return candidate
    except OSError:
        return None
    return None


def list_sessions(workspace: Path, projects_dir: Path | None = None) -> list[SessionInfo]:
    """The conversations Claude Code holds for ``workspace``, the last message most recent first."""
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
            SessionInfo(file.stem, file, *_scan_session(file))
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


def choose_conversation(sessions: list[SessionInfo], remembered_id: str) -> SessionInfo | None:
    """The conversation to select in a workspace: the remembered one if it still exists, else the
    most recent one, else None (no conversation is created)."""
    for session in sessions:
        if session.id == remembered_id:
            return session
    return sessions[0] if sessions else None
