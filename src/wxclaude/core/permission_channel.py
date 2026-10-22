"""How the CLI asks a permission question and how the answer goes back to it.

One channel per message (see ``docs/claude-cli.md``, "Permission channels"). The CLI decides when a
tool needs a permission; the channel only carries the question to the interface, as a
``PermissionRequest`` event, and the answer back. The answer is the same for every channel:
``{"behavior": "allow", "updatedInput": ...}`` or ``{"behavior": "deny", "message": ...}``.
"""

from collections.abc import Callable
from typing import Protocol

from wxclaude.core.errors import RunnerError
from wxclaude.core.events import RunEvent
from wxclaude.core.hook_channel import HookChannel
from wxclaude.core.process_input import ProcessInput

STDIO = "stdio"
HOOK = "hook"
CHANNEL_KINDS = (STDIO, HOOK)
DEFAULT_HOOK_TIMEOUT_SECONDS = 600  # the default of the CLI for its hooks


class PermissionChannel(Protocol):
    """What the runner needs from a channel."""

    def arguments(self) -> list[str]:
        """The arguments of ``claude`` that open this channel."""

    def bind(self, process_input: ProcessInput) -> None:
        """Called once the process runs, with its standard input."""

    def answer(self, request_id: str, decision: dict[str, object]) -> None:
        """Send ``decision`` for the question ``request_id``; raises ``RunnerError``."""

    def close(self) -> None:
        """The process has ended: release what the channel holds."""


class StdioChannel:
    """The CLI asks with ``control_request`` lines on stdout, the answer is a line on stdin."""

    def __init__(self) -> None:
        self._input: ProcessInput | None = None

    def arguments(self) -> list[str]:
        return ["--permission-prompt-tool", "stdio"]

    def bind(self, process_input: ProcessInput) -> None:
        self._input = process_input

    def answer(self, request_id: str, decision: dict[str, object]) -> None:
        if self._input is None:
            raise RunnerError("Claude is not waiting for an answer.")
        self._input.write(
            {
                "type": "control_response",
                "response": {"subtype": "success", "request_id": request_id, "response": decision},
            }
        )

    def close(self) -> None:
        self._input = None


def make_channel(
    kind: str, on_event: Callable[[RunEvent], None], hook_timeout_seconds: int
) -> PermissionChannel:
    """A new channel of ``kind`` (one of ``CHANNEL_KINDS``); raises ``RunnerError``.

    ``on_event`` receives the questions of a channel that does not go through the output of the
    process (the hook); ``hook_timeout_seconds`` is how long the CLI waits for an answer.
    """
    if kind == STDIO:
        return StdioChannel()
    if kind == HOOK:
        return HookChannel(on_event, hook_timeout_seconds)
    raise RunnerError(f"Unknown permission channel: {kind}")
