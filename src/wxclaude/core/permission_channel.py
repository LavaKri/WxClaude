"""How the CLI asks a permission question and how the answer goes back to it.

One channel per message (see ``docs/claude-cli.md``, "Permission channels"). The CLI decides when a
tool needs a permission; the channel only carries the question to the interface, as a
``PermissionRequest`` event, and the answer back. The answer is the same for every channel:
``{"behavior": "allow", "updatedInput": ...}`` or ``{"behavior": "deny", "message": ...}``.
"""

from typing import Protocol

from wxclaude.core.errors import RunnerError
from wxclaude.core.process_input import ProcessInput

STDIO = "stdio"
CHANNEL_KINDS = (STDIO,)


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


def make_channel(kind: str) -> PermissionChannel:
    """A new channel of ``kind`` (one of ``CHANNEL_KINDS``); raises ``RunnerError``."""
    if kind == STDIO:
        return StdioChannel()
    raise RunnerError(f"Unknown permission channel: {kind}")
