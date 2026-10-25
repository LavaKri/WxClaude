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


class FakeView:
    def __init__(self) -> None:
        self.status: list[str] = []
        self.offers = 0

    def set_status(self, text: str) -> None:
        self.status.append(text)

    def claude_not_found(self) -> None:
        self.offers += 1


def _check(available: bool) -> tuple[ClaudeCheck, FakeRunner, FakeView]:
    runner, view = FakeRunner(available), FakeView()
    return ClaudeCheck(runner, lambda: "Ready, gauge at 50 %", view), runner, view


def test_when_claude_is_there_nothing_is_said() -> None:
    check, _runner, view = _check(True)
    assert check.check(offer=True)
    assert view.status == []
    assert view.offers == 0


def test_when_claude_is_missing_the_status_bar_says_so_and_the_user_is_told() -> None:
    check, _runner, view = _check(False)
    assert not check.check(offer=True)
    assert view.status == ["Claude Code not found"]
    assert view.offers == 1


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
