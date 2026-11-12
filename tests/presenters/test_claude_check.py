from collections.abc import Callable

import pytest

from wxclaude.core.claude.runner import ClaudeRunner
from wxclaude.presenters.claude_check import ClaudeCheck

pytestmark = pytest.mark.unit


class FakeRunner(ClaudeRunner):
    def __init__(self, available: bool) -> None:
        super().__init__()
        self.available = available

    def is_available(self) -> bool:
        return self.available

    def base_command(self) -> list[str]:
        return ["claude"]


class FakeView:
    """Records what is said. ``login`` is what the background reading gives (its work is not run:
    it would start the real program)."""

    def __init__(self) -> None:
        self.status: list[str] = []
        self.offers = 0
        self.login_offers = 0
        self.login: bool | None = True
        self.readings = 0

    def set_status(self, text: str) -> None:
        self.status.append(text)

    def claude_not_found(self) -> None:
        self.offers += 1

    def not_logged_in(self) -> None:
        self.login_offers += 1

    def run_in_background(
        self, work: Callable[[], bool | None], done: Callable[[bool | None], None]
    ) -> None:
        self.readings += 1
        done(self.login)


def _check(
    available: bool, *, needs_login: bool = True
) -> tuple[ClaudeCheck, FakeRunner, FakeView]:
    runner, view = FakeRunner(available), FakeView()
    check = ClaudeCheck(runner, lambda: "Ready, gauge at 50 %", view, lambda: needs_login)
    return check, runner, view


def test_when_claude_is_there_and_logged_in_nothing_is_said() -> None:
    check, _runner, view = _check(True)
    assert check.check(offer=True)
    assert view.status == []
    assert (view.offers, view.login_offers) == (0, 0)
    assert view.readings == 1


def test_when_claude_is_missing_the_status_bar_says_so_and_the_user_is_told() -> None:
    check, _runner, view = _check(False)
    assert not check.check(offer=True)
    assert view.status == ["Claude Code not found"]
    assert view.offers == 1
    assert view.readings == 0  # nothing to ask of a program that is not there


def test_without_the_offer_only_the_status_bar_changes() -> None:
    check, _runner, view = _check(False)
    assert not check.check(offer=False)
    assert view.status == ["Claude Code not found"]
    assert view.offers == 0


def test_once_found_the_ready_line_comes_back_and_only_once() -> None:
    check, runner, view = _check(False)
    check.check(offer=True)
    runner.available = True
    assert check.check(offer=False)
    assert view.status == ["Claude Code not found", "Ready, gauge at 50 %"]
    assert check.check(offer=False)
    assert view.status == ["Claude Code not found", "Ready, gauge at 50 %"]  # not repeated


def test_not_logged_in_is_said_in_the_status_bar_and_offered_at_the_start() -> None:
    check, _runner, view = _check(True)
    view.login = False
    assert check.check(offer=True)  # found: True, whatever the login says
    assert view.status == ["Not logged in to Claude Code"]
    assert view.login_offers == 1


def test_without_the_offer_not_logged_in_only_changes_the_status_bar() -> None:
    check, _runner, view = _check(True)
    view.login = False
    check.check(offer=False)
    assert view.status == ["Not logged in to Claude Code"]
    assert view.login_offers == 0


def test_once_logged_in_the_ready_line_comes_back_and_only_once() -> None:
    check, _runner, view = _check(True)
    view.login = False
    check.check(offer=True)
    view.login = True
    check.check(offer=False)
    check.check(offer=False)
    assert view.status == ["Not logged in to Claude Code", "Ready, gauge at 50 %"]


def test_a_login_that_cannot_be_told_says_nothing_and_changes_nothing() -> None:
    check, _runner, view = _check(True)
    view.login = None
    check.check(offer=True)
    assert view.status == []
    assert view.login_offers == 0
    view.login = False
    check.check(offer=False)
    view.login = None
    check.check(offer=False)
    assert view.status == ["Not logged in to Claude Code"]  # the doubt does not undo it


def test_the_login_is_not_asked_when_the_messages_go_to_another_provider() -> None:
    check, _runner, view = _check(True, needs_login=False)
    view.login = False
    assert check.check(offer=True)
    assert view.readings == 0
    assert view.status == []
    assert view.login_offers == 0
