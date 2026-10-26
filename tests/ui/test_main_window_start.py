"""The main window at startup: maximized unless the setting says otherwise."""

from collections.abc import Callable

import pytest
from main_window_support import _runner, _settings

from wxclaude.ui.main_window import MainWindow

pytestmark = pytest.mark.ui


def test_the_window_starts_maximized_by_default(window: MainWindow) -> None:
    assert window.IsMaximized()


def test_the_window_is_not_maximized_when_the_setting_is_off(
    destroy_after: Callable[[MainWindow], MainWindow],
) -> None:
    settings = _settings()
    settings.maximize_at_start = False
    window = destroy_after(MainWindow(settings, _runner()))
    assert not window.IsMaximized()
