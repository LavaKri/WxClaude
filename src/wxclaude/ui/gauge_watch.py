"""The timer that reads the gauges when they are unknown or out of date (see ``GaugeSchedule``)."""

from collections.abc import Callable
from datetime import datetime

import wx

_CHECK_MILLISECONDS = 60_000


class GaugeWatch:
    """Once started, asks ``read`` every minute (and when told to) whether the gauges are to be
    read; ``read(now)`` decides. The application starts it, the tests do not."""

    def __init__(
        self, window: wx.Frame, read: Callable[[datetime], bool], is_closing: Callable[[], bool]
    ) -> None:
        self._window = window
        self._read = read
        self._is_closing = is_closing
        self._timer: wx.Timer | None = None

    def start(self) -> None:
        """Check now and then every minute."""
        if self._timer is not None:
            return
        self._timer = wx.Timer(self._window)
        self._window.Bind(wx.EVT_TIMER, lambda _event: self.check(), self._timer)
        self._timer.Start(_CHECK_MILLISECONDS)
        self.check()

    def check(self) -> None:
        """Read the gauges if they are due (nothing happens before ``start``)."""
        if self._timer is not None and not self._is_closing():
            self._read(datetime.now())

    def stop(self) -> None:
        if self._timer is not None:
            self._timer.Stop()
