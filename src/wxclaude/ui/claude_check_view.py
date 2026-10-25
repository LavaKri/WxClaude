"""The wx side of the check for Claude Code: ``presenters/claude_check.py``."""

from collections.abc import Callable

from wxclaude.i18n import _
from wxclaude.ui.feedback import Feedback


class WxClaudeCheckView:
    """Writes in the status bar and asks, in a message, whether to open the Preferences."""

    def __init__(self, feedback: Feedback, open_preferences: Callable[[], None]) -> None:
        self._feedback = feedback
        self._open_preferences = open_preferences

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
