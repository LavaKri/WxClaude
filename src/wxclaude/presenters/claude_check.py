"""Is Claude Code there? Without it nothing can be answered, and nothing else says so."""

from collections.abc import Callable
from typing import Protocol

from wxclaude.core.claude.runner import ClaudeRunner
from wxclaude.i18n import _


class ClaudeCheckView(Protocol):
    """What the check asks of the interface."""

    def set_status(self, text: str) -> None:
        """Write ``text`` in the message field of the status bar."""
        ...

    def claude_not_found(self) -> None:
        """Tell the user that Claude Code was not found and offer the Preferences."""
        ...


class ClaudeCheck:
    """Looks for Claude Code at the start and when its path changes. While it is missing the
    status bar says so, instead of the "Ready" line."""

    def __init__(
        self, runner: ClaudeRunner, ready_line: Callable[[], str], view: ClaudeCheckView
    ) -> None:
        self._runner = runner
        self._ready_line = ready_line
        self._view = view
        self._missing = False

    def check(self, *, offer: bool) -> bool:
        """Is Claude Code found? If not, the status bar says so and, with ``offer``, the user is
        told how to find it. When it was missing and is found, the "Ready" line comes back."""
        if self._runner.is_available():
            if self._missing:
                self._missing = False
                self._view.set_status(self._ready_line())
            return True
        self._missing = True
        self._view.set_status(_("Claude Code not found"))
        if offer:
            self._view.claude_not_found()
        return False
