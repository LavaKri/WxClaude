"""Reading the gauges of Claude with ``/usage``, and announcing the ones that reach their alert.

Taken out of ``RunPresenter``. A reading is handled like a message: the send buttons are greyed and
the status bar says so until the end, and nothing is announced about the reading itself.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from wxclaude.core.claude.events import GaugesRead, RateWindow, RunEvent
from wxclaude.core.claude.gauge_schedule import GaugeSchedule
from wxclaude.core.claude.runner import ClaudeRunner
from wxclaude.core.claude.usage import GaugeAlerts, UsageTracker
from wxclaude.core.errors import ClaudeNotFoundError, RunnerError
from wxclaude.core.speech.announcements import Announce
from wxclaude.i18n import _

#: The announcement of each gauge that has an alert.
_GAUGE_ALERTS = {"five_hour": Announce.GAUGE_FIVE_HOUR, "seven_day": Announce.GAUGE_WEEKLY}


class GaugeView(Protocol):
    """What the reader asks of the interface (``RunView`` gives it)."""

    def call_after(self, function: Callable[[RunEvent], None], event: RunEvent) -> None:
        """Call ``function(event)`` later on the interface thread (from any thread)."""
        ...

    def say(self, announce: Announce, **values: object) -> None:
        """Announce, where the category of ``announce`` says."""
        ...

    def set_status(self, text: str) -> None:
        """The message field of the status bar."""
        ...


@dataclass(frozen=True, slots=True)
class GaugeLinks:
    """What the reader asks of the presenter: where it works, whether the window is closing, a call
    when the busy state changes, and whether the folder is restricted (not trusted)."""

    workspace: Callable[[], Path | None]
    is_closing: Callable[[], bool]
    state_changed: Callable[[], None]
    restricted: Callable[[], bool]


class GaugeReader:
    """Reads the gauges when they are due and announces those that reach their alert threshold."""

    def __init__(
        self, view: GaugeView, runner: ClaudeRunner, usage: UsageTracker, links: GaugeLinks
    ) -> None:
        self._view = view
        self._runner = runner
        self._usage = usage
        self._links = links
        self._alerts = GaugeAlerts()  # which gauges were announced, for as long as the window lives
        self._schedule = GaugeSchedule()  # when the gauges are read again
        self.refreshing = False  # True while the gauges are read

    def refresh_if_due(self, now: datetime) -> bool:
        """Read the gauges when they are not known or out of date. Nothing is read without a
        workspace, or when the CLI cannot be started (the next try waits longer). True if started.
        The caller makes sure that no message is being answered."""
        workspace = self._links.workspace()
        if workspace is None or not self._schedule.due(self._usage.windows.values(), now):
            return False
        try:
            restricted = self._links.restricted()
            self._runner.read_usage(workspace, self._post_reading, restricted=restricted)
        except ClaudeNotFoundError, RunnerError:
            self._schedule.finished(self._usage.windows.values(), now, ok=False)
            return False
        self.refreshing = True
        self._view.set_status(_("Refreshing the gauges"))
        self._links.state_changed()
        return True

    def alert(self, windows: tuple[RateWindow, ...]) -> None:
        """Announce the gauges that just reached their alert threshold (once per crossing)."""
        for window in self._alerts.update(windows):
            announce = _GAUGE_ALERTS.get(window.name)
            if announce is not None and window.utilization is not None:
                self._view.say(announce, percent=round(window.utilization * 100))

    # -- inside ---------------------------------------------------------------------------

    def _post_reading(self, event: RunEvent) -> None:
        """Called by the thread of the reading: hand the end of it over to the interface thread."""
        self._view.call_after(self._finish, event)

    def _finish(self, read: RunEvent) -> None:
        """The reading ended (or failed): the gauges are kept if it gave any, nothing is said."""
        if self._links.is_closing() or not isinstance(read, GaugesRead):
            return
        self.refreshing = False
        now = datetime.now()
        if read.windows:
            self._usage.record_windows(read.windows, now)
        self._schedule.finished(self._usage.windows.values(), now, ok=bool(read.windows))
        self._links.state_changed()
        self._view.set_status(self._usage.ready_line())
        self.alert(read.windows)
