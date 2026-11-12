"""The wx side of the check for Claude Code: ``presenters/claude_check.py``."""

from collections.abc import Callable

from wxclaude.i18n import _
from wxclaude.ui.feedback import Feedback
from wxclaude.ui.worker import run_in_background


class WxClaudeCheckView:
    """Writes in the status bar and asks, in a message, whether to open the Preferences or the
    sign-in; ``alive`` tells whether the window is still there."""

    def __init__(
        self,
        feedback: Feedback,
        open_preferences: Callable[[], None],
        open_sign_in: Callable[[], None],
        alive: Callable[[], bool] = lambda: True,
    ) -> None:
        self._feedback = feedback
        self._open_preferences = open_preferences
        self._open_sign_in = open_sign_in
        self._alive = alive

    def set_status(self, text: str) -> None:
        self._feedback.set_status(text)

    def claude_not_found(self) -> None:
        """The message is read first (No is the default button); Yes opens the Preferences."""
        message = _(
            "Claude Code was not found on this computer.\n\n"
            "Install it, or give its path in File > Preferences > Claude."
        )
        if self._feedback.confirm(
            _("Claude Code not found"),
            message,
            yes_label=_("&Open the Preferences"),
            no_label=_("&Close"),
        ):
            self._open_preferences()

    def not_logged_in(self) -> None:
        """The message is read first (No is the default button); Yes opens the sign-in."""
        message = _(
            "Claude Code is not logged in: no message can be answered until you sign in.\n\n"
            "You can also sign in later, with Tools > Sign in to Claude…"
        )
        if self._feedback.confirm(
            _("Not logged in to Claude Code"),
            message,
            yes_label=_("&Sign in…"),
            no_label=_("&Close"),
        ):
            self._open_sign_in()

    def run_in_background(
        self, work: Callable[[], bool | None], done: Callable[[bool | None], None]
    ) -> None:
        run_in_background(
            work,
            done,
            lambda _message: None,  # nothing of ours is raised: an unreadable answer is None
            name="claude-login-check",
            alive=self._alive,
        )
