"""Keyboard shortcuts: the configurable commands, the rules a shortcut must follow, conflicts.

A shortcut is written ``Ctrl+Shift+O``: optional modifiers (``Ctrl``, ``Alt``, ``Shift``, in this
order) then a key name. The empty string means "no shortcut".
"""

import enum
import re
from collections.abc import Mapping
from dataclasses import dataclass

from wxclaude.i18n import N_

_MODIFIER_ORDER = ("Ctrl", "Alt", "Shift")
_NAMED_KEYS = (
    "Enter",
    "Space",
    "Tab",
    "Esc",
    "Home",
    "End",
    "PageUp",
    "PageDown",
    "Up",
    "Down",
    "Left",
    "Right",
    "Delete",
    "Insert",
    "Backspace",
)
_FUNCTION_KEY = re.compile(r"F([1-9]|1[0-2])")
_LETTER_OR_DIGIT = re.compile(r"[A-Z0-9]")

#: Keys that are never allowed: they move the focus or close dialogs, and Insert is the modifier
#: key of screen readers.
_RESERVED_KEYS = frozenset({"Tab", "Esc", "Insert"})

#: Shortcuts of the standard commands, which cannot be changed or reused.
FIXED_SHORTCUTS = frozenset(
    {
        "Ctrl+Q",
        "Alt+F4",
        "Ctrl+Z",
        "Ctrl+Y",
        "Ctrl+X",
        "Ctrl+C",
        "Ctrl+V",
        "Ctrl+A",
        "Ctrl+Tab",
        "Ctrl+Shift+Tab",
        "Ctrl+PageUp",
        "Ctrl+PageDown",
        "F10",  # activates the menu bar
        "Shift+F10",  # opens the context menu
        # Access keys of the menu bar (French and English): File/Fichier, Conversation,
        # Tools/Outils, Help/Aide.
        "Alt+F",
        "Alt+C",
        "Alt+T",
        "Alt+O",
        "Alt+H",
        "Alt+A",
    }
)


@dataclass(frozen=True, slots=True)
class ConfigurableCommand:
    """A command whose shortcut the user can change; ``label`` is a message id."""

    id: str
    label: str
    default: str = ""


OPEN_WORKSPACE_COMMAND = ConfigurableCommand("workspace.open", N_("Open workspace"), "Ctrl+O")
NEW_CONVERSATION_COMMAND = ConfigurableCommand("conversation.new", N_("New conversation"), "Ctrl+N")
RESUME_CONVERSATION_COMMAND = ConfigurableCommand(
    "conversation.resume", N_("Resume a conversation"), "Ctrl+Shift+O"
)
REFRESH_CONVERSATION_COMMAND = ConfigurableCommand(
    "conversation.refresh", N_("Refresh the conversation"), "F5"
)
FIND_COMMAND = ConfigurableCommand("search.find", N_("Find in the conversation"), "Ctrl+F")
FIND_NEXT_COMMAND = ConfigurableCommand("search.next", N_("Find next"), "F3")
FIND_PREVIOUS_COMMAND = ConfigurableCommand("search.previous", N_("Find previous"), "Shift+F3")
INTERRUPT_COMMAND = ConfigurableCommand("claude.interrupt", N_("Interrupt Claude"), "Ctrl+Shift+I")
#: The same shortcut as the task list of the Claude Code CLI.
TASKS_COMMAND = ConfigurableCommand("tasks.list", N_("Task list"), "Ctrl+T")
SEND_COMMAND = ConfigurableCommand("prompt.send", N_("Send the prompt"), "Ctrl+Enter")
SEND_ALTERNATIVE_COMMAND = ConfigurableCommand(
    "prompt.send_alternative", N_("Send the prompt with the alternative agent"), "Shift+Enter"
)

#: Every configurable command, in the order of the Shortcuts list.
CONFIGURABLE_COMMANDS = (
    OPEN_WORKSPACE_COMMAND,
    NEW_CONVERSATION_COMMAND,
    RESUME_CONVERSATION_COMMAND,
    REFRESH_CONVERSATION_COMMAND,
    FIND_COMMAND,
    FIND_NEXT_COMMAND,
    FIND_PREVIOUS_COMMAND,
    INTERRUPT_COMMAND,
    TASKS_COMMAND,
    SEND_COMMAND,
    SEND_ALTERNATIVE_COMMAND,
)


class ShortcutProblem(enum.Enum):
    """Why a shortcut is refused."""

    INVALID = "invalid"
    RESERVED = "reserved"
    FIXED = "fixed"
    TAKEN = "taken"


@dataclass(frozen=True, slots=True)
class ShortcutCheck:
    """Outcome of ``check_shortcut``: no problem, or the problem and what it collides with."""

    problem: ShortcutProblem | None = None
    other: ConfigurableCommand | None = None  # the command already using it (TAKEN)


def normalize_shortcut(text: str) -> str | None:
    """Canonical spelling of ``text`` (``ctrl + shift + o`` -> ``Ctrl+Shift+O``), None if invalid.

    The empty string is valid and stands for "no shortcut".
    """
    text = text.strip()
    if not text:
        return ""
    parts = [part.strip() for part in text.split("+")]
    if "" in parts:
        return None
    *modifiers, key = parts
    names = {name.lower(): name for name in _MODIFIER_ORDER}
    chosen = set()
    for modifier in modifiers:
        name = names.get(modifier.lower())
        if name is None or name in chosen:
            return None
        chosen.add(name)
    normalized_key = _normalize_key(key)
    if normalized_key is None:
        return None
    ordered = [name for name in _MODIFIER_ORDER if name in chosen]
    return "+".join([*ordered, normalized_key])


def _normalize_key(key: str) -> str | None:
    upper = key.upper()
    if _FUNCTION_KEY.fullmatch(upper) or _LETTER_OR_DIGIT.fullmatch(upper):
        return upper
    for name in _NAMED_KEYS:
        if name.lower() == key.lower():
            return name
    return None


def check_shortcut(
    command: ConfigurableCommand, shortcut: str, current: Mapping[str, str]
) -> ShortcutCheck:
    """Can ``command`` use ``shortcut``? ``current`` maps command ids to their shortcut.

    Rules: it must be well formed; a function key (F1 to F12) is allowed alone or with any
    modifiers; Enter needs at least one modifier (alone it adds a line break); any other key
    needs Ctrl, Alt or both (Shift may be added; a plain letter would block typing); Tab, Esc
    and Insert are never allowed; it must not be the shortcut of a standard command or the
    access key of a menu, nor of another configurable command.
    """
    normalized = normalize_shortcut(shortcut)
    if normalized is None:
        return ShortcutCheck(ShortcutProblem.INVALID)
    if not normalized:
        return ShortcutCheck()
    *modifiers, key = normalized.split("+")
    if key in _RESERVED_KEYS:
        return ShortcutCheck(ShortcutProblem.RESERVED)
    is_function_key = bool(_FUNCTION_KEY.fullmatch(key))
    if key == "Enter":
        if not modifiers:
            return ShortcutCheck(ShortcutProblem.RESERVED)
    elif not is_function_key and not {"Ctrl", "Alt"} & set(modifiers):
        return ShortcutCheck(ShortcutProblem.RESERVED)
    if normalized in FIXED_SHORTCUTS:
        return ShortcutCheck(ShortcutProblem.FIXED)
    for other in CONFIGURABLE_COMMANDS:
        if other.id != command.id and current.get(other.id, other.default) == normalized:
            return ShortcutCheck(ShortcutProblem.TAKEN, other)
    return ShortcutCheck()
