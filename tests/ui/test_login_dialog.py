from collections.abc import Callable

import pytest
import wx

from wxclaude.core.claude.auth import ClaudeLogin, LoginEnded, LoginEvent
from wxclaude.core.claude.status import ClaudeStatus
from wxclaude.ui.login_dialog import LoginDialog

pytestmark = pytest.mark.ui

SIGNED_OUT = ClaudeStatus(found=True, path="claude", version="2.1.286", logged_in=False)


class FakeLogin(ClaudeLogin):
    def __init__(self) -> None:
        super().__init__()
        self.emails: list[str] = []
        self.callback: Callable[[LoginEvent], None] | None = None
        self.cancelled = 0

    def start(self, on_event: Callable[[LoginEvent], None], email: str = "") -> None:
        self.emails.append(email)
        self.callback = on_event

    def cancel(self) -> None:
        self.cancelled += 1


def _click(button: wx.Button) -> None:
    button.GetEventHandler().ProcessEvent(wx.CommandEvent(wx.wxEVT_BUTTON, button.GetId()))


@pytest.fixture
def made(destroy_after: Callable[[LoginDialog], LoginDialog]) -> tuple[LoginDialog, FakeLogin]:
    login = FakeLogin()
    dialog = destroy_after(LoginDialog(None, login, lambda: SIGNED_OUT))
    return dialog, login


def test_the_state_of_claude_code_is_shown_when_the_dialog_opens(
    made: tuple[LoginDialog, FakeLogin],
) -> None:
    dialog, _login = made
    assert "Connection: not logged in" in dialog._state.GetValue()


def test_every_field_has_an_accessible_name(made: tuple[LoginDialog, FakeLogin]) -> None:
    dialog, _login = made
    assert dialog._state.GetName() == "State of Claude Code"
    assert dialog._email.GetName() == "E-mail address (optional, not remembered)"
    assert dialog._progress.GetName() == "Sign-in progress"
    assert dialog._address.GetName() == "Address of the sign-in page"


def test_before_signing_in_only_the_sign_in_works(made: tuple[LoginDialog, FakeLogin]) -> None:
    dialog, _login = made
    assert dialog._sign_in.IsEnabled()
    assert not dialog._cancel.IsEnabled()
    assert not dialog._copy.IsEnabled()


def test_signing_in_gives_the_address_and_greys_what_cannot_be_used(
    made: tuple[LoginDialog, FakeLogin],
) -> None:
    dialog, login = made
    dialog._email.SetValue("  someone@example.com ")
    _click(dialog._sign_in)
    assert login.emails == ["someone@example.com"]
    assert not dialog._sign_in.IsEnabled()
    assert not dialog._email.IsEnabled()
    assert dialog._cancel.IsEnabled()
    assert dialog._progress.GetValue()


def test_the_address_of_the_page_can_be_copied_once_it_is_known(
    made: tuple[LoginDialog, FakeLogin], monkeypatch: pytest.MonkeyPatch
) -> None:
    dialog, login = made
    copied: list[str] = []

    def set_clipboard(text: str) -> bool:
        copied.append(text)
        return True

    monkeypatch.setattr("wxclaude.ui.login_dialog.desktop.set_clipboard", set_clipboard)
    dialog._presenter.sign_in("")
    assert not dialog._copy.IsEnabled()
    dialog.show_url("https://claude.example/authorize")
    assert dialog._address.GetValue() == "https://claude.example/authorize"
    assert dialog._copy.IsEnabled()
    dialog._on_copy()
    assert copied == ["https://claude.example/authorize"]
    assert login.emails == [""]


def test_a_cancelled_sign_in_gives_the_dialog_back_and_says_so(
    made: tuple[LoginDialog, FakeLogin],
) -> None:
    dialog, login = made
    dialog._presenter.sign_in("")
    _click(dialog._cancel)
    assert login.cancelled == 1
    dialog._presenter._on_event(LoginEnded(succeeded=False, cancelled=True, output=""))
    assert dialog._sign_in.IsEnabled()
    assert not dialog._cancel.IsEnabled()
    assert dialog._progress.GetValue() == "The sign-in was cancelled."
