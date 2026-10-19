"""The messages of a conversation.

A message is what the display shows (a prompt or an answer) plus what it keeps without showing it
(tools used, tool results, thinking, token usage).
"""

from dataclasses import dataclass, field
from enum import StrEnum


class Role(StrEnum):
    """Who wrote a message."""

    USER = "user"
    ASSISTANT = "assistant"


@dataclass(slots=True)
class Usage:
    """Token counts reported by Claude for one answer."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass(slots=True)
class ToolUse:
    """A tool call made by Claude, with its result once known."""

    id: str
    name: str
    input: dict[str, object] = field(default_factory=dict)
    result: str = ""
    is_error: bool = False


@dataclass(slots=True)
class Message:
    """A prompt or an answer.

    ``model`` is None for a prompt and for answers without a model (synthetic ones). ``effort``
    is the one the answer was generated with (the ``effort`` field of the assistant entries of the
    session file; the stream does not report it). A ``hidden`` message is noise that is not
    displayed unless an option asks for it.
    """

    id: str
    role: Role
    text: str
    model: str | None = None
    effort: str | None = None
    hidden: bool = False
    tools: list[ToolUse] = field(default_factory=list)
    thinking: list[str] = field(default_factory=list)
    usage: Usage | None = None
