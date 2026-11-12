"""The reader of the gauges on its own: what happens when the end of a reading arrives late.

The readings through ``RunPresenter`` (when they are due, what is said) are in
``test_run_presenter_gauges.py``.
"""

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pytest

from wxclaude.core.claude.events import GaugesRead, PermissionExpired, RateWindow, RunEvent
from wxclaude.core.claude.runner import ClaudeRunner
from wxclaude.core.claude.usage import UsageTracker
from wxclaude.core.speech.announcements import Announce
from wxclaude.presenters.gauge_reader import GaugeLinks, GaugeReader

pytestmark = pytest.mark.unit

FULL = RateWindow("five_hour", 0.95, 0)


class FakeView:
    def __init__(self) -> None:
        self.said: list[Announce] = []
        self.status: list[str] = []

    def call_after(self, function: Callable[[RunEvent], None], event: RunEvent) -> None:
        function(event)

    def say(self, announce: Announce, **values: object) -> None:
        self.said.append(announce)

    def set_status(self, text: str) -> None:
        self.status.append(text)


class FakeRunner(ClaudeRunner):
    def __init__(self) -> None:
        super().__init__()
        self.callback: Callable[[RunEvent], None] | None = None

    def read_usage(
        self, cwd: Path, on_event: Callable[[RunEvent], None], *, restricted: bool = False
    ) -> None:
        self.callback = on_event


class Setup:
    def __init__(self, tmp_path: Path) -> None:
        self.view = FakeView()
        self.runner = FakeRunner()
        self.usage = UsageTracker()
        self.closing = False
        self.changes = 0
        links = GaugeLinks(
            workspace=lambda: tmp_path,
            is_closing=lambda: self.closing,
            state_changed=self._changed,
            restricted=lambda: False,
        )
        self.reader = GaugeReader(self.view, self.runner, self.usage, links)

    def _changed(self) -> None:
        self.changes += 1

    def start_reading(self) -> Callable[[RunEvent], None]:
        assert self.reader.refresh_if_due(datetime.now())
        assert self.runner.callback is not None
        return self.runner.callback


def test_the_end_of_a_reading_is_used_when_the_window_is_open(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    finish = setup.start_reading()
    finish(GaugesRead((FULL,)))
    assert not setup.reader.refreshing
    assert setup.usage.windows == {"five_hour": FULL}
    assert setup.view.said == [Announce.GAUGE_FIVE_HOUR]


def test_the_end_of_a_reading_is_dropped_when_the_window_is_closing(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    finish = setup.start_reading()
    changes = setup.changes
    setup.closing = True
    finish(GaugesRead((FULL,)))
    assert setup.usage.windows == {}
    assert setup.view.said == []
    assert setup.changes == changes  # the window is going away: nothing is told to it


def test_an_event_that_is_not_the_end_of_a_reading_is_ignored(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    finish = setup.start_reading()
    finish(PermissionExpired("r1", "Bash"))
    assert setup.reader.refreshing  # the reading is still going on
    assert setup.usage.windows == {}
