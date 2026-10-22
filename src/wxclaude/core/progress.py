"""What the interface says about a run: progress while it goes, and how it ended."""

import enum
from dataclasses import dataclass, field

from wxclaude.core.announcements import Announce
from wxclaude.core.events import (
    AssistantText,
    PermissionDenied,
    RunEvent,
    Thinking,
    ToolUsed,
    TurnEnded,
    TurnResult,
)


@dataclass(frozen=True, slots=True)
class Progress:
    """An announcement to make (status bar, and screen reader if progress is announced)."""

    announce: Announce
    values: dict[str, object] = field(default_factory=dict)


def progress_for(event: RunEvent) -> Progress | None:
    """The progress an event stands for, None for the events that say nothing."""
    if isinstance(event, Thinking):
        return Progress(Announce.CLAUDE_THINKING)
    if isinstance(event, ToolUsed):
        return Progress(Announce.CLAUDE_USING_TOOL, {"tool": event.name})
    if isinstance(event, AssistantText):
        return Progress(Announce.CLAUDE_ANSWERING)
    if isinstance(event, PermissionDenied) and event.reason_type != "hook":
        return Progress(Announce.PERMISSION_DENIED, {"tool": event.tool_name})
    return None


class Outcome(enum.Enum):
    """How a run ended."""

    DONE = "done"
    INTERRUPTED = "interrupted"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class TurnOutcome:
    """The outcome of a run; ``details`` explains a failure (for the dialog)."""

    outcome: Outcome
    details: str = ""


def turn_outcome(result: TurnResult | None, ended: TurnEnded) -> TurnOutcome:
    """Decide how a run ended from its result line (if any) and the end of the process."""
    if ended.interrupted:
        return TurnOutcome(Outcome.INTERRUPTED)
    if result is not None and result.is_error:
        return TurnOutcome(Outcome.FAILED, result.text or result.subtype)
    if result is not None and ended.exit_code == 0:
        return TurnOutcome(Outcome.DONE)
    details = [ended.stderr, *ended.diagnostics]
    text = "\n".join(part for part in details if part)
    if not text:
        text = f"exit code {ended.exit_code}"
    return TurnOutcome(Outcome.FAILED, text)
