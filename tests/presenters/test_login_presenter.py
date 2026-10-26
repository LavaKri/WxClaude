from collections.abc import Callable

import pytest

from wxclaude.core.claude.auth import ClaudeLogin, LoginEnded, LoginEvent, LoginUrl
from wxclaude.core.claude.status import ClaudeStatus
from wxclaude.core.errors import ClaudeLoginError
from wxclaude.presenters.login_presenter import LoginPresenter

pytestmark = pytest.mark.unit

SIGNED_IN = ClaudeStatus(found=True, path="claude", version="2.1.286", logged_in=True)
SIGNED_OUT = ClaudeStatus(found=True, path="claude", version="2.1.286", logged_in=False)


class FakeLogin(ClaudeLogin):
    """Keeps the callback and the e-mail; the test ends the sign-in by hand."""

    def __init__(self, refuse: bool = False) -> None:
        super().__init__()
        self.refuse = refuse
        self.emails: list[str] = []
        self.callback: Callable[[LoginEvent], None] | None = None
        self.cancelled = 0
        self.running = False

    @property
    def is_running(self) -> bool:
        return self.running

    def start(self, on_event: Callable[[LoginEvent], None], email: str = "") -> None:
        if self.refuse:
            raise ClaudeLoginError("no claude here")
        self.emails.append(email)
        self.callback = on_event
        self.running = True

    def cancel(self) -> None:
        self.cancelled += 1

    def emit(self, event: LoginEvent) -> None:
        assert self.callback is not None
        self.callback(event)


class FakeView:
    def __init__(self) -> None:
        self.states: list[str] = []
        self.progress: list[str] = []
        self.running: list[bool] = []
        self.urls: list[str] = []
        self.told: list[str] = []
        self.errors: list[str] = []

    def call_after(self, function: Callable[[LoginEvent], None], event: LoginEvent) -> None:
        function(event)  # the interface thread is this one

    def set_state(self, text: str) -> None:
        self.states.append(text)

    def set_progress(self, text: str) -> None:
        self.progress.append(text)

    def set_running(self, running: bool) -> None:
        self.running.append(running)

    def show_url(self, url: str) -> None:
        self.urls.append(url)

    def tell(self, text: str) -> None:
        self.told.append(text)

    def show_error(self, message: str) -> None:
        self.errors.append(message)


def _presenter(
    status: ClaudeStatus = SIGNED_IN, refuse: bool = False
) -> tuple[LoginPresenter, FakeLogin, FakeView]:
    login, view = FakeLogin(refuse), FakeView()
    return LoginPresenter(login, view, lambda: status), login, view


def test_opening_shows_the_state_of_claude_code() -> None:
    presenter, _login, view = _presenter()
    presenter.open()
    assert "Connection: logged in" in view.states[0]


def test_signing_in_passes_the_address_and_shows_that_it_waits() -> None:
    presenter, login, view = _presenter()
    presenter.sign_in("someone@example.com")
    assert login.emails == ["someone@example.com"]
    assert view.running == [True]
    assert "browser" in view.progress[-1]


def test_the_address_of_the_page_is_given_to_the_view() -> None:
    presenter, login, view = _presenter()
    presenter.sign_in("")
    login.emit(LoginUrl("https://claude.example/authorize"))
    assert view.urls == ["https://claude.example/authorize"]


def test_a_sign_in_that_worked_is_said_once_the_state_confirms_it() -> None:
    presenter, login, view = _presenter(SIGNED_IN)
    presenter.sign_in("")
    login.emit(LoginEnded(succeeded=True, cancelled=False, output="Login successful."))
    assert view.running == [True, False]
    assert view.told == ["You are signed in to Claude Code."]
    assert view.errors == []
    assert "Connection: logged in" in view.states[-1]


def test_a_sign_in_that_ends_well_but_is_not_confirmed_is_an_error() -> None:
    presenter, login, view = _presenter(SIGNED_OUT)
    presenter.sign_in("")
    login.emit(LoginEnded(succeeded=True, cancelled=False, output=""))
    assert view.told == []
    assert "does not say that you are signed in" in view.errors[0]
    assert "Connection: not logged in" in view.states[-1]


def test_a_failed_sign_in_shows_what_the_command_printed() -> None:
    presenter, login, view = _presenter(SIGNED_OUT)
    presenter.sign_in("")
    login.emit(LoginEnded(succeeded=False, cancelled=False, output="Login failed."))
    assert view.told == []
    assert "Login failed." in view.errors[0]


def test_a_cancelled_sign_in_says_so_without_an_error() -> None:
    presenter, login, view = _presenter()
    presenter.sign_in("")
    presenter.cancel()
    login.emit(LoginEnded(succeeded=False, cancelled=True, output=""))
    assert login.cancelled == 1
    assert view.running == [True, False]
    assert view.progress[-1] == "The sign-in was cancelled."
    assert view.errors == []
    assert view.told == []


def test_a_command_that_cannot_start_is_told_and_nothing_runs() -> None:
    presenter, _login, view = _presenter(refuse=True)
    presenter.sign_in("")
    assert "no claude here" in view.errors[0]
    assert view.running == []


def test_after_closing_what_comes_is_ignored_and_the_command_is_stopped() -> None:
    presenter, login, view = _presenter()
    presenter.sign_in("")
    presenter.close()
    login.emit(LoginEnded(succeeded=True, cancelled=False, output=""))
    login.emit(LoginUrl("https://claude.example/authorize"))
    assert login.cancelled == 1
    assert view.running == [True]
    assert view.errors == []
    assert view.told == []
    assert view.urls == []
