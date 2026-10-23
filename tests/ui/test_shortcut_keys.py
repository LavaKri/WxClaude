"""The shortcut typed in the Shortcuts page, read from the wx key event."""

import pytest
import wx

from wxclaude.ui.shortcut_keys import key_name, shortcut_from_event

pytestmark = pytest.mark.ui


def _event(code: int, *, ctrl: bool = False, alt: bool = False, shift: bool = False) -> wx.KeyEvent:
    event = wx.KeyEvent(wx.wxEVT_KEY_DOWN)
    event.SetKeyCode(code)
    event.SetControlDown(ctrl)
    event.SetAltDown(alt)
    event.SetShiftDown(shift)
    return event


def test_the_modifiers_and_the_key_make_the_shortcut(wx_app: wx.App) -> None:
    assert shortcut_from_event(_event(ord("O"), ctrl=True, shift=True)) == "Ctrl+Shift+O"
    assert shortcut_from_event(_event(wx.WXK_DOWN, alt=True)) == "Alt+Down"
    assert shortcut_from_event(_event(wx.WXK_F2)) == "F2"
    assert shortcut_from_event(_event(wx.WXK_NUMPAD_ENTER, ctrl=True)) == "Ctrl+Enter"


def test_a_modifier_alone_or_an_unknown_key_is_no_shortcut(wx_app: wx.App) -> None:
    assert shortcut_from_event(_event(wx.WXK_CONTROL, ctrl=True)) is None
    assert shortcut_from_event(_event(wx.WXK_SHIFT, shift=True)) is None
    assert shortcut_from_event(_event(wx.WXK_F13)) is None


@pytest.mark.parametrize(
    ("code", "name"),
    [(ord("A"), "A"), (ord("7"), "7"), (wx.WXK_F12, "F12"), (wx.WXK_PAGEUP, "PageUp")],
)
def test_the_keys_have_their_names(code: int, name: str) -> None:
    assert key_name(code) == name
