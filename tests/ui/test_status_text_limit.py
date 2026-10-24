"""Tests of the main window: no field of the status bar holds more than 200 characters."""

import pytest

from wxclaude.core.speech.announcements import Announce
from wxclaude.ui.main_window import MainWindow

pytestmark = pytest.mark.ui

LONG = "word " * 100  # 500 characters


def test_every_field_is_cut_at_200_characters(window: MainWindow) -> None:
    feedback = window._feedback
    feedback.set_status(LONG)
    feedback.show_step(LONG)
    feedback.show_position(1, 1)
    bar = window.GetStatusBar()
    assert len(bar.GetStatusText(2)) == 200
    assert bar.GetStatusText(2).endswith("…")
    assert len(bar.GetStatusText(1)) == 200
    assert bar.GetStatusText(0) == "Message 1 of 1"


def test_an_announcement_with_a_long_value_is_cut_in_the_status_bar(window: MainWindow) -> None:
    window._feedback.say(Announce.CLAUDE_USING_TOOL, tool="T" * 500)
    text = window.GetStatusBar().GetStatusText(2)
    assert len(text) == 200
    assert text.endswith("…")


def test_a_short_text_is_not_touched(window: MainWindow) -> None:
    window._feedback.set_status("Ready, gauge at 50 %")
    assert window.GetStatusBar().GetStatusText(2) == "Ready, gauge at 50 %"
