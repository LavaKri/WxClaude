from datetime import datetime, timedelta

import pytest

from wxclaude.core.claude.events import RateWindow
from wxclaude.core.claude.gauge_schedule import GaugeSchedule

pytestmark = pytest.mark.unit

NOW = datetime(2026, 10, 23, 10, 0)


def _window(name: str, resets_in: timedelta | None) -> RateWindow:
    return RateWindow(name, 0.5, None if resets_in is None else int((NOW + resets_in).timestamp()))


def test_unknown_gauges_are_read() -> None:
    assert GaugeSchedule().due([], NOW)


def test_known_gauges_are_read_again_once_a_reset_time_is_past() -> None:
    schedule = GaugeSchedule()
    ahead = [_window("five_hour", timedelta(hours=1)), _window("seven_day", timedelta(days=2))]
    assert not schedule.due(ahead, NOW)
    assert not schedule.due(ahead, NOW + timedelta(minutes=59))
    assert schedule.due(ahead, NOW + timedelta(hours=1))


def test_the_gauges_that_the_reading_does_not_give_do_not_count() -> None:
    old = [_window("seven_day_opus", timedelta(hours=-5)), _window("five_hour", None)]
    assert not GaugeSchedule().due(old, NOW)


def test_after_a_failure_the_wait_doubles_up_to_ten_minutes() -> None:
    schedule = GaugeSchedule()
    waits = []
    for _try in range(6):
        schedule.finished([], NOW, ok=False)
        minutes = 0
        while not schedule.due([], NOW + timedelta(minutes=minutes)):
            minutes += 1
        waits.append(minutes)
    assert waits == [1, 2, 4, 8, 10, 10]


def test_a_good_reading_ends_the_wait() -> None:
    schedule = GaugeSchedule()
    schedule.finished([], NOW, ok=False)
    schedule.finished([_window("five_hour", timedelta(hours=3))], NOW, ok=True)
    assert schedule.due([], NOW)  # nothing known: read at once


def test_a_reading_that_still_shows_a_past_reset_counts_as_a_failure() -> None:
    schedule = GaugeSchedule()
    stale = [_window("five_hour", timedelta(hours=-1))]
    schedule.finished(stale, NOW, ok=True)
    assert not schedule.due(stale, NOW)
    assert schedule.due(stale, NOW + timedelta(minutes=1))
