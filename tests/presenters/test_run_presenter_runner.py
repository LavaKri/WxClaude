"""What the window asks of the runner through ``RunPresenter``: the claude program to start, and
the stop when it closes (the window does not reach into ``runner`` itself)."""

from pathlib import Path

import pytest
from test_run_presenter import FakeRunner
from test_run_presenter_security import presenter_for

pytestmark = pytest.mark.unit


def test_the_claude_path_is_the_one_of_the_runner(tmp_path: Path) -> None:
    presenter, runner, _view = presenter_for(tmp_path, None)
    assert presenter.claude_path == ""
    presenter.claude_path = "C:/tools/claude.exe"
    assert runner.claude_path == "C:/tools/claude.exe"
    runner.claude_path = ""
    assert presenter.claude_path == ""


def test_the_claude_path_follows_a_runner_that_is_replaced(tmp_path: Path) -> None:
    presenter, _runner, _view = presenter_for(tmp_path, None)
    other = FakeRunner()
    presenter.runner = other
    presenter.claude_path = "D:/claude.exe"
    assert other.claude_path == "D:/claude.exe"


def test_stopping_interrupts_the_runner_without_a_word(tmp_path: Path) -> None:
    presenter, runner, view = presenter_for(tmp_path, None)
    assert not presenter.busy  # nothing is being answered: interrupt() would do nothing
    presenter.stop()
    assert runner.interrupts == 1
    assert view.said == []
