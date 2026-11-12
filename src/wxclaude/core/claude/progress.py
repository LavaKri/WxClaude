"""What the interface says about a run: progress while it goes, and how it ended."""

import enum
from dataclasses import dataclass, field

from wxclaude.core.claude.events import (
    ApiRetry,
    AssistantText,
    Compacted,
    McpServer,
    PermissionDenied,
    RunEvent,
    Thinking,
    ToolUsed,
    TurnEnded,
    TurnResult,
)
from wxclaude.core.claude.tool_target import tool_detail
from wxclaude.core.config.agents import mode_from_cli
from wxclaude.core.numbers import format_tokens
from wxclaude.core.speech.announcements import Announce
from wxclaude.i18n import _


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
        values: dict[str, object] = {"tool": event.name}
        detail = tool_detail(event.name, event.input)
        if detail is not None:  # only the history says more: what is said does not change
            values.update(history_as=detail[0], target=detail[1])
        return Progress(Announce.CLAUDE_USING_TOOL, values)
    if isinstance(event, AssistantText):
        return Progress(Announce.CLAUDE_ANSWERING)
    if isinstance(event, PermissionDenied) and event.reason_type != "hook":
        return Progress(Announce.PERMISSION_DENIED, {"tool": event.tool_name})
    return None


def retry_progress(event: ApiRetry) -> Progress:
    """The server returned an error and the CLI will ask again: say what and which retry."""
    if event.error:
        reason = event.error.replace("_", " ")
    elif event.status is not None:
        reason = _("status {status}").format(status=event.status)
    else:
        reason = _("unknown error")
    return Progress(
        Announce.SERVER_RETRY,
        {"reason": reason, "attempt": event.attempt, "total": event.max_retries},
    )


def compaction_progress(event: Compacted) -> Progress:
    """The CLI compacted the conversation: what Claude kept is only a summary."""
    trigger = _("automatic") if event.trigger == "auto" else _("manual")
    if event.pre_tokens is None or event.post_tokens is None:
        return Progress(Announce.CONVERSATION_COMPACTED_UNKNOWN, {"trigger": trigger})
    return Progress(
        Announce.CONVERSATION_COMPACTED,
        {
            "trigger": trigger,
            "before": format_tokens(event.pre_tokens),
            "after": format_tokens(event.post_tokens),
        },
    )


def mode_progress(asked: str, reported: str, *, masked: bool) -> Progress | None:
    """Did the CLI run the message in another permission mode than ``asked`` (our name for it)?

    ``reported`` is the mode of its ``system/init`` line. None when it is the one asked for, and
    when nothing was asked or reported. ``masked`` is a launch with the credentials hidden from the
    tools of Claude, which makes the CLI force the manual mode.
    """
    if not asked or not reported:
        return None
    actual = mode_from_cli(reported)
    if actual == asked:
        return None
    if masked and actual == "manual":
        return Progress(Announce.MODE_FORCED_MANUAL, {"asked": asked})
    return Progress(Announce.MODE_DIFFERENT, {"actual": actual, "asked": asked})


_MCP_NOTICES = {"failed": Announce.MCP_SERVER_FAILED, "pending": Announce.MCP_SERVER_SLOW}


def mcp_progress(servers: tuple[McpServer, ...], reported: dict[str, str]) -> list[Progress]:
    """What to say about the MCP servers of a start: those that failed, or are slow to start.

    A server is told about once for each state it is in: ``reported`` (name to state, kept by the
    caller from one message to the next, and updated here) stops a broken server from being
    announced at each message, and lets it be announced again if it works, then fails again.
    """
    notices: list[Progress] = []
    for server in servers:
        announce = _MCP_NOTICES.get(server.status)
        if announce is None:
            reported.pop(server.name, None)  # it works (or the state is not one we know)
        elif reported.get(server.name) != server.status:
            reported[server.name] = server.status
            notices.append(Progress(announce, {"server": server.name}))
    return notices


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


# Lines the CLI writes on stderr with a server that is not Anthropic's: they are not errors and
# must not be taken for the cause of one.
_NOTICE_PREFIXES = (
    "[claude-code:unrecognized_model]",
    "⚠ claude.ai connectors are disabled",  # a provider's key takes precedence over the login
)


def without_notices(stderr: str) -> str:
    """``stderr`` without the notices of the CLI that are not errors."""
    lines = [line for line in stderr.splitlines() if not line.startswith(_NOTICE_PREFIXES)]
    return "\n".join(lines).strip()


def turn_outcome(
    result: TurnResult | None, ended: TurnEnded, refused: ApiRetry | None = None
) -> TurnOutcome:
    """Decide how a run ended from its result line (if any) and the end of the process.

    ``refused`` is the retry that showed the server refusing the credentials: the run was stopped
    for that, which is a failure and not an interruption by the user.
    """
    if refused is not None:
        return TurnOutcome(
            Outcome.FAILED,
            _(
                "The server refused the credentials (error {status}). Check the key of the "
                "provider in the Preferences, page Providers, or sign in to Claude again."
            ).format(status=refused.status),
        )
    if ended.interrupted:
        return TurnOutcome(Outcome.INTERRUPTED)
    if result is not None and result.subtype == "error_max_turns":
        # ``num_turns`` is not the limit (the CLI counts one more), so no number is given.
        return TurnOutcome(
            Outcome.FAILED,
            _("The limit of turns was reached. Send a new message to continue."),
        )
    if result is not None and result.is_error:
        return TurnOutcome(Outcome.FAILED, result.text or result.subtype)
    if result is not None and ended.exit_code == 0:
        return TurnOutcome(Outcome.DONE)
    details = [without_notices(ended.stderr), *ended.diagnostics]
    text = "\n".join(part for part in details if part)
    if not text:
        text = f"exit code {ended.exit_code}"
    return TurnOutcome(Outcome.FAILED, text)
