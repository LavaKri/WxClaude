"""Reading the gauges with ``/usage``: handled like a message, silent, with a fake runner."""

from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fake_claude_files import FakeClaudeFiles

from wxclaude.core.claude.events import GaugesRead, RateWindow, RunEvent
from wxclaude.core.claude.runner import ClaudeRunner
from wxclaude.core.claude.usage import UsageTracker
from wxclaude.core.config.settings import Settings
from wxclaude.core.errors import ClaudeNotFoundError
from wxclaude.core.speech.announcements import Announce
from wxclaude.presenters.run_presenter import RunLinks, RunPresenter
from wxclaude.presenters.shared import Shared

pytestmark = pytest.mark.unit

NOW = datetime(2026, 10, 23, 10, 0)
FIVE_HOURS = RateWindow("five_hour", 0.5, int((NOW + timedelta(hours=3)).timestamp()))
WEEK = RateWindow("seven_day", 0.2, int((NOW + timedelta(days=2)).timestamp()))


class FakeView:
    """Records what is said and shown; nothing else is used by a reading."""

    def __init__(self) -> None:
        self.said: list[Announce] = []
        self.status: list[str] = []
        self.errors: list[str] = []

    def call_after(self, function: Callable[[RunEvent], None], event: RunEvent) -> None:
        function(event)

    def say(self, announce: Announce, **values: object) -> None:
        self.said.append(announce)

    def set_status(self, text: str) -> None:
        self.status.append(text)

    def show_error(self, message: str) -> None:
        self.errors.append(message)


class FakeRunner(ClaudeRunner):
    """Keeps the callback of a reading instead of starting a process."""

    def __init__(self) -> None:
        super().__init__()
        self.reads: list[Path] = []
        self.callback: Callable[[RunEvent], None] | None = None
        self.start_error: Exception | None = None
        self.interrupted = 0

    def read_usage(self, cwd: Path, on_event: Callable[[RunEvent], None]) -> None:
        if self.start_error is not None:
            raise self.start_error
        self.reads.append(cwd)
        self.callback = on_event

    def interrupt(self) -> None:
        self.interrupted += 1


class Setup:
    """A presenter with a fake view, a fake runner and a workspace that can be taken away."""

    def __init__(self, workspace: Path | None) -> None:
        self.view = FakeView()
        self.runner = FakeRunner()
        self.usage = UsageTracker()
        self.workspace = workspace
        self.changes = 0
        shared = Shared(Settings.load(None), self.usage, FakeClaudeFiles())
        links = RunLinks(
            workspace=lambda: self.workspace,
            conversation_id=lambda: "c",
            conversation_name=lambda: "",
            fork_from=lambda: "",
            is_closing=lambda: False,
            state_changed=self._changed,
        )
        self.presenter = RunPresenter(self.view, self.runner, shared, links)  # type: ignore[arg-type]

    def _changed(self) -> None:
        self.changes += 1

    def end_reading(self, *windows: RateWindow) -> None:
        assert self.runner.callback is not None
        self.runner.callback(GaugesRead(windows))


@pytest.fixture
def setup(tmp_path: Path) -> Setup:
    return Setup(tmp_path)


def test_a_reading_greys_what_a_message_greys_and_says_so_in_the_status_bar(setup: Setup) -> None:
    assert setup.presenter.refresh_gauges_if_due(NOW)
    presenter = setup.presenter
    assert (presenter.busy, presenter.refreshing) == (True, True)
    assert setup.view.status == ["Refreshing the gauges"]
    assert setup.changes == 1
    setup.end_reading(FIVE_HOURS, WEEK)
    assert (presenter.busy, presenter.refreshing) == (False, False)
    assert setup.changes == 2
    assert setup.view.status[-1] == "Ready, gauge at 50 %"
    assert setup.usage.windows == {"five_hour": FIVE_HOURS, "seven_day": WEEK}
    assert (setup.view.said, setup.view.errors) == ([], [])


def test_nothing_is_read_without_a_workspace(setup: Setup) -> None:
    setup.workspace = None
    assert not setup.presenter.refresh_gauges_if_due(NOW)
    assert (setup.runner.reads, setup.presenter.busy) == ([], False)


def test_nothing_is_read_twice_at_once(setup: Setup) -> None:
    assert setup.presenter.refresh_gauges_if_due(NOW)
    assert not setup.presenter.refresh_gauges_if_due(NOW + timedelta(minutes=5))
    assert len(setup.runner.reads) == 1


def test_known_gauges_are_not_read_until_a_reset_time_is_past(setup: Setup) -> None:
    setup.usage.record_windows((FIVE_HOURS, WEEK), NOW)
    assert not setup.presenter.refresh_gauges_if_due(NOW + timedelta(hours=2))
    assert setup.presenter.refresh_gauges_if_due(NOW + timedelta(hours=3))


def test_a_failed_reading_is_silent_and_keeps_the_gauges(setup: Setup) -> None:
    setup.usage.record_windows((FIVE_HOURS,), NOW)
    assert setup.presenter.refresh_gauges_if_due(NOW + timedelta(hours=4))
    setup.end_reading()
    assert not setup.presenter.busy
    assert setup.usage.windows == {"five_hour": FIVE_HOURS}
    assert setup.view.status[-1] == "Ready, gauge at 50 %"
    assert (setup.view.said, setup.view.errors) == ([], [])


def test_a_cli_that_cannot_start_is_silent_and_tried_again_later(setup: Setup) -> None:
    setup.runner.start_error = ClaudeNotFoundError("no claude")
    assert not setup.presenter.refresh_gauges_if_due(NOW)
    assert (setup.presenter.busy, setup.view.status, setup.view.errors) == (False, [], [])
    setup.runner.start_error = None
    assert not setup.presenter.refresh_gauges_if_due(NOW + timedelta(seconds=30))  # waiting
    assert setup.presenter.refresh_gauges_if_due(NOW + timedelta(minutes=1))


def test_the_interrupt_stops_the_reading_without_a_word(setup: Setup) -> None:
    setup.presenter.refresh_gauges_if_due(NOW)
    setup.presenter.interrupt()
    assert setup.runner.interrupted == 1
    assert setup.view.said == []
    setup.end_reading()  # what the runner does after the process was killed
    assert not setup.presenter.busy


def test_a_gauge_over_its_threshold_is_announced_once(setup: Setup) -> None:
    high = RateWindow("five_hour", 0.95, FIVE_HOURS.resets_at)
    week = RateWindow("seven_day", 0.3, WEEK.resets_at)
    setup.presenter.refresh_gauges_if_due(NOW)
    setup.end_reading(high, week)
    assert setup.view.said == [Announce.GAUGE_FIVE_HOUR, Announce.GAUGE_WEEKLY]
    setup.usage.windows.clear()
    setup.presenter.refresh_gauges_if_due(NOW + timedelta(minutes=10))
    setup.end_reading(high, week)
    assert setup.view.said == [Announce.GAUGE_FIVE_HOUR, Announce.GAUGE_WEEKLY]  # not again
