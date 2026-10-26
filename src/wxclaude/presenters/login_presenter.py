"""Signing in to Claude Code from WxClaude: starting the command, following it, saying the result.

The command works in a thread (``core/claude/auth.py``); its events are handed over to the
interface thread by the view (``LoginView.call_after``). Nothing here touches wx.
"""

from collections.abc import Callable
from typing import Protocol

from wxclaude.core.claude.auth import ClaudeLogin, LoginEnded, LoginEvent, LoginUrl
from wxclaude.core.claude.status import ClaudeStatus, describe_status
from wxclaude.core.errors import ClaudeLoginError
from wxclaude.i18n import _


class LoginView(Protocol):
    """What the presenter asks of the sign-in dialog."""

    def call_after(self, function: Callable[[LoginEvent], None], event: LoginEvent) -> None:
        """Call ``function(event)`` later on the interface thread (from any thread)."""
        ...

    def set_state(self, text: str) -> None:
        """The state of Claude Code (found, version, connection)."""
        ...

    def set_progress(self, text: str) -> None:
        """What the sign-in is doing ('' when it is not running)."""
        ...

    def set_running(self, running: bool) -> None:
        """A sign-in starts or ends: the controls that start it or stop it follow."""
        ...

    def show_url(self, url: str) -> None:
        """The address of the sign-in page, for a browser that did not open by itself."""
        ...

    def tell(self, text: str) -> None:
        """Tell the user the result, so that a screen reader reads it."""
        ...

    def show_error(self, message: str) -> None:
        """Tell the user that something failed."""
        ...


class LoginPresenter:
    """One sign-in at a time, shown through ``view``. ``read_state`` asks Claude Code its state."""

    def __init__(
        self, login: ClaudeLogin, view: LoginView, read_state: Callable[[], ClaudeStatus]
    ) -> None:
        self._login = login
        self._view = view
        self._read_state = read_state
        self._closed = False

    @property
    def is_running(self) -> bool:
        return self._login.is_running

    def open(self) -> None:
        """The dialog opens: show the state of Claude Code."""
        self._view.set_state(describe_status(self._read_state()))

    def sign_in(self, email: str) -> None:
        """Start the sign-in; the browser opens by itself. ``email`` may be empty."""
        try:
            self._login.start(self._post, email)
        except ClaudeLoginError as error:
            self._view.show_error(_("The sign-in cannot be started.\n{error}").format(error=error))
            return
        self._view.set_running(True)
        self._view.set_progress(_("Finish the sign-in in the browser. Waiting for it to end."))

    def cancel(self) -> None:
        """Stop the sign-in that runs (its end is then reported as a cancellation)."""
        self._login.cancel()

    def close(self) -> None:
        """The dialog closes: stop what runs and ignore what comes after."""
        self._closed = True
        self._login.cancel()

    def _post(self, event: LoginEvent) -> None:
        """Called by the thread of the command: hand the event over to the interface thread."""
        self._view.call_after(self._on_event, event)

    def _on_event(self, event: LoginEvent) -> None:
        if self._closed:
            return
        if isinstance(event, LoginUrl):
            self._view.show_url(event.url)
        elif isinstance(event, LoginEnded):
            self._finish(event)

    def _finish(self, ended: LoginEnded) -> None:
        """The texts are set before ``set_running(False)``: the focus comes back to the dialog
        then, and a screen reader reads what is there."""
        if ended.cancelled:
            self._view.set_progress(_("The sign-in was cancelled."))
            self._view.set_running(False)
            return
        self._view.set_progress("")
        state = self._read_state()
        self._view.set_state(describe_status(state))
        self._view.set_running(False)
        if ended.succeeded and state.logged_in is True:
            self._view.tell(_("You are signed in to Claude Code."))
        elif ended.succeeded:
            self._view.show_error(
                _("The sign-in ended, but Claude Code does not say that you are signed in.")
            )
        else:
            self._view.show_error(_("The sign-in failed.\n{details}").format(details=ended.output))
