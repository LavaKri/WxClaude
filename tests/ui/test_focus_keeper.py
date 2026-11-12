"""The return of the focus after Alt+Tab (docs/focus.md, rule E): windows are real, the events of
activation are simulated."""

from collections.abc import Iterator

import pytest
import wx

from wxclaude.ui.focus_keeper import FocusKeeper

pytestmark = pytest.mark.ui


class _Setup:
    def __init__(self) -> None:
        self.closing = False
        self.frame = wx.Frame(None)
        self.default = wx.TextCtrl(self.frame)  # stands for the prompt
        self.first = wx.TextCtrl(self.frame)
        self.second = wx.TextCtrl(self.frame)
        self.interrupt = wx.Button(self.frame, label="Interrupt")
        self.keeper = FocusKeeper(self.frame, lambda: self.closing, lambda: self.default)
        self.frame.Show()

    def activate(self, active: bool) -> None:
        event = wx.ActivateEvent(wx.wxEVT_ACTIVATE, active)
        self.frame.GetEventHandler().ProcessEvent(event)
        wx.Yield()  # not SafeYield: it disables the windows, which the keeper reads as a dialog

    def away_and_back(self) -> None:
        self.activate(False)
        self.activate(True)


@pytest.fixture
def setup(wx_app: wx.App) -> Iterator[_Setup]:
    setup = _Setup()
    yield setup
    setup.frame.Destroy()


def test_the_control_that_had_the_focus_gets_it_back(setup: _Setup) -> None:
    setup.second.SetFocus()
    setup.activate(False)
    setup.first.SetFocus()  # something else took the focus meanwhile
    setup.activate(True)
    assert setup.second.HasFocus()


def test_a_button_is_not_returned_to_the_default_control_is(setup: _Setup) -> None:
    setup.interrupt.SetFocus()
    setup.away_and_back()
    assert setup.default.HasFocus()


def test_a_control_that_is_greyed_meanwhile_gives_the_default_control(setup: _Setup) -> None:
    setup.second.SetFocus()
    setup.activate(False)
    setup.second.Disable()
    setup.activate(True)
    assert setup.default.HasFocus()


def test_a_control_that_is_hidden_meanwhile_gives_the_default_control(setup: _Setup) -> None:
    setup.second.SetFocus()
    setup.activate(False)
    setup.second.Hide()
    setup.activate(True)
    assert setup.default.HasFocus()


def test_what_was_remembered_is_used_once_and_never_kept(setup: _Setup) -> None:
    setup.second.SetFocus()
    setup.away_and_back()
    setup.first.SetFocus()  # the application moves the focus
    setup.activate(True)  # an activation that was not preceded by a deactivation
    assert setup.first.HasFocus()


def test_a_window_blocked_by_a_dialog_is_not_an_alt_tab(setup: _Setup) -> None:
    setup.second.SetFocus()
    setup.frame.Disable()  # what a modal dialog does to its parent
    setup.activate(False)
    setup.frame.Enable()
    setup.first.SetFocus()  # the dialog gave the focus back, the application moved it (rule B)
    setup.activate(True)
    assert setup.first.HasFocus()


def test_nothing_is_done_while_the_window_closes(setup: _Setup) -> None:
    setup.second.SetFocus()
    setup.activate(False)
    setup.first.SetFocus()
    setup.closing = True
    setup.activate(True)
    assert setup.first.HasFocus()
