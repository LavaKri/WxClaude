"""When the gauges are read again with ``/usage`` (see ``docs/claude-cli.md``).

A reading is due when no gauge is known yet, or when a gauge has passed its reset time (the value
shown is then out of date). After a failure, or a reading that still shows a reset time in the past,
the next try waits longer each time (1, 2, 4, 8 then 10 minutes at most), so a missing or broken
CLI is not started again every minute.
"""

from collections.abc import Iterable
from datetime import datetime, timedelta

from wxclaude.core.claude.events import RateWindow
from wxclaude.core.claude.usage_text import READ_WINDOWS

_LONGEST_WAIT = timedelta(minutes=10)
#: The timer is not exact: a wait of one minute must be met by the next tick.
_SLACK = timedelta(seconds=10)


def _out_of_date(windows: Iterable[RateWindow], now: datetime) -> bool:
    """Has a gauge that the reading can replace passed its reset time?"""
    return any(
        window.name in READ_WINDOWS
        and window.resets_at is not None
        and window.resets_at <= now.timestamp()
        for window in windows
    )


class GaugeSchedule:
    """Decides when to read the gauges and how long to wait after a failure."""

    def __init__(self) -> None:
        self._failures = 0
        self._not_before: datetime | None = None

    def due(self, windows: Iterable[RateWindow], now: datetime) -> bool:
        """Should the gauges be read now? ``windows`` are the ones known."""
        if self._not_before is not None and now < self._not_before:
            return False
        known = list(windows)
        return not known or _out_of_date(known, now)

    def finished(self, windows: Iterable[RateWindow], now: datetime, *, ok: bool) -> None:
        """A reading ended; ``windows`` are the gauges known after it."""
        if ok and not _out_of_date(windows, now):
            self._failures = 0
            self._not_before = None
            return
        self._failures += 1
        wait = min(timedelta(minutes=2 ** (self._failures - 1)), _LONGEST_WAIT)
        self._not_before = now + wait - _SLACK
