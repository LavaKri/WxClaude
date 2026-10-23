"""The events a run of Claude sends to the interface (typed, no wx).

They come from the ``stream-json`` output of the CLI (see ``stream.py``) and from the end of the
process (``TurnEnded``, always the last one).
"""

from dataclasses import dataclass, field

from wxclaude.core.conversation.messages import Usage


@dataclass(frozen=True, slots=True)
class SessionInit:
    """The CLI has started: the session, the model and the permission mode really used."""

    session_id: str
    model: str
    permission_mode: str


@dataclass(frozen=True, slots=True)
class Thinking:
    """Claude is thinking (``tokens`` is an estimate, None when unknown)."""

    tokens: int | None = None


@dataclass(frozen=True, slots=True)
class AssistantText:
    """A complete block of text of the answer."""

    text: str
    model: str | None


@dataclass(frozen=True, slots=True)
class ToolUsed:
    """Claude calls a tool."""

    tool_id: str
    name: str
    input: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolResult:
    """The result of a tool call came back."""

    tool_id: str
    is_error: bool


@dataclass(frozen=True, slots=True)
class PermissionDenied:
    """A tool was not allowed to run.

    ``reason_type`` is the ``decision_reason_type`` of the CLI: ``hook`` when our own answer
    refused the tool (the user was told already), ``mode`` for ``dontAsk``, '' when not given.
    """

    tool_name: str
    message: str
    reason_type: str = ""


@dataclass(frozen=True, slots=True)
class PermissionRequest:
    """Claude asks whether a tool may run; the answer goes back with ``ClaudeRunner``.

    ``suggested_rule`` is the rule the CLI proposes to remember (``Bash(touch x)``), '' if none.
    """

    request_id: str
    tool_name: str
    tool_use_id: str
    input: dict[str, object]
    description: str
    blocked_path: str
    suggested_rule: str


@dataclass(frozen=True, slots=True)
class PermissionExpired:
    """The CLI stopped waiting for the answer to a permission question and denied the tool.

    Only the hook channel has a waiting time; the question can no longer be answered.
    """

    request_id: str
    tool_name: str


@dataclass(frozen=True, slots=True)
class RateWindow:
    """One usage gauge: a window (``five_hour``, ``seven_day``...), how full it is (a fraction
    between 0 and 1) and when it resets (seconds since the epoch)."""

    name: str
    utilization: float | None
    resets_at: int | None


@dataclass(frozen=True, slots=True)
class RateLimit:
    """The state of the usage gauges of the subscription, with the window that was just used."""

    status: str
    limit_type: str
    windows: tuple[RateWindow, ...]


@dataclass(frozen=True, slots=True)
class TurnResult:
    """The final result line of the CLI."""

    is_error: bool
    subtype: str
    text: str
    usage: Usage | None
    duration_ms: int | None
    cost_usd: float | None
    num_turns: int | None


@dataclass(frozen=True, slots=True)
class TurnEnded:
    """The process has ended and all its output was read. Always the last event of a run.

    ``diagnostics`` holds what the CLI wrote that is not a stream line (lines that are not JSON).
    """

    exit_code: int | None
    interrupted: bool
    stderr: str
    diagnostics: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class GaugesRead:
    """The end of a reading of the gauges (``/usage``); ``windows`` is empty when it failed."""

    windows: tuple[RateWindow, ...]


RunEvent = (
    SessionInit
    | Thinking
    | AssistantText
    | ToolUsed
    | ToolResult
    | PermissionDenied
    | PermissionRequest
    | PermissionExpired
    | RateLimit
    | TurnResult
    | TurnEnded
    | GaugesRead
)
