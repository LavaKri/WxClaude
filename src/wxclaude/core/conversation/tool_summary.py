"""The line under an answer that sums up the tools Claude used to give it.

``5 commands run, 2 files modified, 3 files read, 1 other tool used, of which 1 failed``: the
commands (Bash, PowerShell), the files modified (Edit, Write, NotebookEdit; each file once, however
many times it was changed), the files read (Read, each file once) and every other tool; what is
zero is left out, and nothing at all is written when the answer used no tool. The failures are the
tools whose result is an error (a denied permission is one).
"""

from collections.abc import Iterable, Sequence

from wxclaude.core.conversation.messages import ToolUse
from wxclaude.i18n import _, ngettext

_COMMANDS = frozenset({"Bash", "PowerShell"})
_MODIFYING = frozenset({"Edit", "Write", "NotebookEdit"})
_READING = frozenset({"Read"})
_PATH_KEYS = ("file_path", "notebook_path", "path")


def _path_of(tool: ToolUse) -> str | None:
    """The file a tool worked on, written the same way whatever the case and the separators."""
    for key in _PATH_KEYS:
        value = tool.input.get(key)
        if isinstance(value, str) and value:
            return value.replace("\\", "/").casefold()
    return None


def _files(tools: Iterable[ToolUse]) -> int:
    """How many files the tools worked on: each path once, a tool without a path as one file."""
    paths: set[str] = set()
    unnamed = 0
    for tool in tools:
        path = _path_of(tool)
        if path is None:
            unnamed += 1
        else:
            paths.add(path)
    return len(paths) + unnamed


def _part(singular: str, plural: str, count: int) -> list[str]:
    """The text for ``count`` things (in the right number), nothing if there are none."""
    return [ngettext(singular, plural, count).format(count=count)] if count else []


def summarize_tools(tools: Sequence[ToolUse]) -> str:
    """The summary line of an answer that used ``tools``; '' if it used none."""
    named = _COMMANDS | _MODIFYING | _READING
    texts = [
        *_part(
            "{count} command run",
            "{count} commands run",
            sum(1 for tool in tools if tool.name in _COMMANDS),
        ),
        *_part(
            "{count} file modified",
            "{count} files modified",
            _files(tool for tool in tools if tool.name in _MODIFYING),
        ),
        *_part(
            "{count} file read",
            "{count} files read",
            _files(tool for tool in tools if tool.name in _READING),
        ),
        *_part(
            "{count} other tool used",
            "{count} other tools used",
            sum(1 for tool in tools if tool.name not in named),
        ),
    ]
    if not texts:
        return ""
    failed = sum(1 for tool in tools if tool.is_error)
    if failed:
        texts.append(_("of which {count} failed").format(count=failed))
    return ", ".join(texts)
