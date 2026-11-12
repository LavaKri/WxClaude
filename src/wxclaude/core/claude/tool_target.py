"""What a tool call works on, for the announcement history: ``Edit`` on ``build.bat``.

Only what is useful and safe to keep is given: the name of a file (not its folder), the program a
command starts (never the whole command: it may hold a key or a password), the pattern of a search,
the host of a web address, the query of a web search, the description of a task for an agent.
Nothing is said about a tool that has none of these.
"""

from pathlib import PureWindowsPath
from urllib.parse import urlsplit

from wxclaude.core.speech.announcements import Announce

MAX_TARGET_LENGTH = 60

_FILE_TOOLS = frozenset({"Edit", "Write", "Read", "NotebookEdit", "MultiEdit"})
_COMMAND_TOOLS = frozenset({"Bash", "PowerShell"})
_PATH_KEYS = ("file_path", "notebook_path", "path")
_OTHER_KEYS = {
    "Grep": "pattern",
    "Glob": "pattern",
    "WebSearch": "query",
    "Task": "description",
    "Agent": "description",
}


def _string(tool_input: dict[str, object], *keys: str) -> str:
    """The first of ``keys`` that holds a text that is not empty, trimmed."""
    for key in keys:
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _shorten(text: str) -> str:
    text = " ".join(text.split())  # one line
    if len(text) <= MAX_TARGET_LENGTH:
        return text
    return text[: MAX_TARGET_LENGTH - 1] + "…"


def _program(command: str) -> str:
    """The program a command starts: its first word, without quotes or folder."""
    words = command.split()
    if not words:
        return ""
    word = words[0].strip("\"'")
    return PureWindowsPath(word).name or word


def tool_detail(name: str, tool_input: dict[str, object]) -> tuple[Announce, str] | None:
    """The message for the history and the target of the call, None if there is nothing to add."""
    if name in _FILE_TOOLS:
        path = _string(tool_input, *_PATH_KEYS)
        target = (PureWindowsPath(path).name or path) if path else ""
        return _on(target)
    if name in _COMMAND_TOOLS:
        program = _program(_string(tool_input, "command"))
        return (Announce.CLAUDE_USING_TOOL_TO_RUN, _shorten(program)) if program else None
    if name == "WebFetch":
        return _on(urlsplit(_string(tool_input, "url")).hostname or "")
    key = _OTHER_KEYS.get(name)
    return _on(_string(tool_input, key)) if key else None


def _on(target: str) -> tuple[Announce, str] | None:
    return (Announce.CLAUDE_USING_TOOL_ON, _shorten(target)) if target else None
