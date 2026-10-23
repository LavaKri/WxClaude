"""Reading the gauges in the real window, with the fake claude: the interface follows."""

from datetime import datetime
from pathlib import Path

import pytest
from main_window_support import _wait_until_idle

from wxclaude.ui.main_window import MainWindow

pytestmark = pytest.mark.ui


def test_while_the_gauges_are_read_the_sending_and_the_usage_are_greyed(
    conversation: MainWindow,
) -> None:
    window = conversation
    assert window._run.refresh_gauges_if_due(datetime.now())
    assert not window.can_send
    assert not window._menu.usage_item.IsEnabled()
    assert window._menu.interrupt_item.IsEnabled()
    assert window.GetStatusBar().GetStatusText(2) == "Refreshing the gauges"
    _wait_until_idle(window)
    assert window.can_send
    assert window._menu.usage_item.IsEnabled()
    assert not window._menu.interrupt_item.IsEnabled()
    # the alerts of the fake gauges (over their thresholds) are said, not written
    assert window.GetStatusBar().GetStatusText(2) == "Ready, gauge at 96 %"


def test_the_gauges_are_not_read_without_a_workspace(window: MainWindow) -> None:
    assert not window._run.refresh_gauges_if_due(datetime.now())
    assert window._menu.usage_item.IsEnabled()


def test_the_watch_reads_the_gauges_at_once_and_when_a_workspace_opens_later(
    tmp_path: Path, window: MainWindow
) -> None:
    window.gauge_watch.start()  # no workspace yet: nothing to read
    assert not window._run.busy
    window.open_workspace(tmp_path)
    assert window._run.refreshing
    _wait_until_idle(window)
    assert "five_hour" in window._usage.windows
    window.gauge_watch.stop()


def test_the_window_does_not_read_the_gauges_by_itself(tmp_path: Path, window: MainWindow) -> None:
    window.open_workspace(tmp_path)
    assert not window._run.busy  # only start_gauge_watch (the application) starts the reading
