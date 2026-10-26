"""Dialog to sign in to Claude Code: the view of ``presenters/login_presenter.py``.

The browser opens by itself; the dialog waits for it and says the result. Everything is reachable
by keyboard. The state of Claude Code has the focus when the dialog opens, and while a sign-in runs
the focus is on its progress, so a screen reader reads what to do.
"""

from collections.abc import Callable

import wx

from wxclaude.core.claude.auth import ClaudeLogin, LoginEvent
from wxclaude.core.claude.status import ClaudeStatus
from wxclaude.core.labels import accessible_name
from wxclaude.i18n import _
from wxclaude.presenters.login_presenter import LoginPresenter
from wxclaude.ui import desktop
from wxclaude.ui.fields import read_only_field


class LoginDialog(wx.Dialog):
    """State of Claude Code, an optional e-mail address (not remembered), and the buttons that
    start, cancel and close. The address of the page is there for a browser that did not open."""

    def __init__(
        self, parent: wx.Window, login: ClaudeLogin, read_state: Callable[[], ClaudeStatus]
    ) -> None:
        super().__init__(parent, title=_("Sign in to Claude Code"), style=wx.DEFAULT_DIALOG_STYLE)
        self._presenter = LoginPresenter(login, self, read_state)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self._state = self._add_field(sizer, _("State of Claude Code"), 5)
        email_text = _("&E-mail address (optional, not remembered)")
        self._add_label(sizer, email_text)
        self._email = wx.TextCtrl(self, name=accessible_name(email_text))
        sizer.Add(self._email, 0, wx.EXPAND | wx.ALL, 8)
        self._progress = self._add_field(sizer, _("Sign-in progress"), 2)
        self._address = self._add_field(sizer, _("Address of the sign-in page"), 3)

        self._sign_in = wx.Button(self, label=_("&Sign in"))
        self._copy = wx.Button(self, label=_("Copy the &address"))
        self._cancel = wx.Button(self, label=_("&Cancel the sign-in"))
        close = wx.Button(self, wx.ID_CLOSE)
        self._sign_in.SetDefault()
        self._sign_in.Bind(wx.EVT_BUTTON, lambda _event: self._presenter.sign_in(self.email))
        self._copy.Bind(wx.EVT_BUTTON, lambda _event: self._on_copy())
        self._cancel.Bind(wx.EVT_BUTTON, lambda _event: self._presenter.cancel())
        close.Bind(wx.EVT_BUTTON, lambda _event: self._on_close())
        self.Bind(wx.EVT_CLOSE, lambda _event: self._on_close())
        self.SetEscapeId(wx.ID_CLOSE)
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        for button in (self._sign_in, self._copy, self._cancel, close):
            buttons.Add(button, 0, wx.RIGHT, 6)
        sizer.Add(buttons, 0, wx.ALL, 8)
        self.SetSizerAndFit(sizer)

        self._url = ""
        self.set_running(False)
        self._presenter.open()
        self._state.SetFocus()

    @property
    def email(self) -> str:
        return str(self._email.GetValue()).strip()

    def _add_label(self, sizer: wx.BoxSizer, text: str) -> None:
        """A label, created right before its control so that screen readers pair them."""
        sizer.Add(wx.StaticText(self, label=text), 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)

    def _add_field(self, sizer: wx.BoxSizer, text: str, lines: int) -> wx.TextCtrl:
        self._add_label(sizer, text)
        field = read_only_field(self, lines, name=accessible_name(text))
        field.SetMinSize(wx.Size(field.GetCharWidth() * 70, field.GetMinSize().GetHeight()))
        sizer.Add(field, 0, wx.EXPAND | wx.ALL, 8)
        return field

    def _on_copy(self) -> None:
        if not desktop.set_clipboard(self._url):
            self.show_error(_("The address could not be copied."))

    def _on_close(self) -> None:
        """Closing stops a sign-in that is still running."""
        self._presenter.close()
        self.EndModal(wx.ID_CLOSE)

    # The view of the presenter ------------------------------------------------------------------

    def call_after(self, function: Callable[[LoginEvent], None], event: LoginEvent) -> None:
        wx.CallAfter(function, event)

    def set_state(self, text: str) -> None:
        self._state.SetValue(text)

    def set_progress(self, text: str) -> None:
        self._progress.SetValue(text)

    def set_running(self, running: bool) -> None:
        """While a sign-in runs only Cancel and Close work, and the focus is on the progress. At
        the end the focus goes to the progress if it says something (a cancellation), else to the
        state."""
        self._sign_in.Enable(not running)
        self._email.Enable(not running)
        self._cancel.Enable(running)
        self._copy.Enable(False)  # until the address of the page is known
        self._url = ""
        self._address.SetValue("")
        if running or self._progress.GetValue():
            self._progress.SetFocus()
        else:
            self._state.SetFocus()

    def show_url(self, url: str) -> None:
        self._url = url
        self._address.SetValue(url)
        self._copy.Enable(True)

    def tell(self, text: str) -> None:
        self._message(text, _("Information"), wx.ICON_INFORMATION)

    def show_error(self, message: str) -> None:
        self._message(message, _("Error"), wx.ICON_ERROR)

    def _message(self, message: str, caption: str, icon: int) -> None:
        with wx.MessageDialog(self, message, caption, wx.OK | icon) as dialog:
            dialog.ShowModal()
