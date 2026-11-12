"""Is Claude Code there, and logged in? Without it nothing can be answered, and nothing else says
so: the status bar says it, and the start offers what to do."""

from collections.abc import Callable
from typing import Protocol

from wxclaude.core.claude.runner import ClaudeRunner
from wxclaude.core.claude.status import read_login
from wxclaude.core.errors import ClaudeNotFoundError
from wxclaude.i18n import _


class ClaudeCheckView(Protocol):
    """What the check asks of the interface."""

    def set_status(self, text: str) -> None:
        """Write ``text`` in the message field of the status bar."""
        ...

    def claude_not_found(self) -> None:
        """Tell the user that Claude Code was not found and offer the Preferences."""
        ...

    def not_logged_in(self) -> None:
        """Tell the user that Claude Code is not logged in and offer to sign in."""
        ...

    def run_in_background(
        self, work: Callable[[], bool | None], done: Callable[[bool | None], None]
    ) -> None:
        """Run ``work`` away from the window thread, then ``done(its result)`` in it (nothing
        is called once the window is gone)."""
        ...


class ClaudeCheck:
    """Looks for Claude Code at the start and when its path changes, then asks it whether it is
    logged in. While it is missing, or not logged in, the status bar says so instead of the
    "Ready" line. ``needs_login`` tells whether the login of Claude matters: not when the messages
    go to another provider, which has its own key."""

    def __init__(
        self,
        runner: ClaudeRunner,
        ready_line: Callable[[], str],
        view: ClaudeCheckView,
        needs_login: Callable[[], bool] = lambda: True,
    ) -> None:
        self._runner = runner
        self._ready_line = ready_line
        self._view = view
        self._needs_login = needs_login
        self._missing = False
        self._logged_out = False

    def check(self, *, offer: bool) -> bool:
        """Is Claude Code found? If not, the status bar says so and, with ``offer``, the user is
        told how to find it. When it was missing and is found, the "Ready" line comes back. If it
        is found, whether it is logged in is asked in the background (``_login_known``)."""
        if not self._runner.is_available():
            self._missing = True
            self._view.set_status(_("Claude Code not found"))
            if offer:
                self._view.claude_not_found()
            return False
        if self._missing:
            self._missing = False
            self._view.set_status(self._ready_line())
        self._check_login(offer=offer)
        return True

    def _check_login(self, *, offer: bool) -> None:
        if not self._needs_login():
            return
        try:
            command = self._runner.base_command()
        except ClaudeNotFoundError:
            return  # it went away since: the next check says so
        self._view.run_in_background(
            lambda: read_login(command), lambda logged_in: self._login_known(logged_in, offer)
        )

    def _login_known(self, logged_in: bool | None, offer: bool) -> None:
        """The answer of ``auth status``: False says so in the status bar and, with ``offer``,
        offers to sign in; True brings the "Ready" line back if it had said otherwise; None (not
        told) changes nothing."""
        if logged_in is False:
            self._logged_out = True
            self._view.set_status(_("Not logged in to Claude Code"))
            if offer:
                self._view.not_logged_in()
        elif logged_in is True and self._logged_out:
            self._logged_out = False
            self._view.set_status(self._ready_line())
