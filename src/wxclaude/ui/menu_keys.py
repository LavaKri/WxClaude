"""The keys that ask for a context menu."""

import wx


def is_shift_f10(event: wx.KeyEvent) -> bool:
    return event.GetKeyCode() == wx.WXK_F10 and event.ShiftDown() and not event.ControlDown()


def is_menu_key(event: wx.KeyEvent) -> bool:
    """The keys that ask for a context menu: Applications, and Shift+F10."""
    return event.GetKeyCode() == wx.WXK_WINDOWS_MENU or is_shift_f10(event)
