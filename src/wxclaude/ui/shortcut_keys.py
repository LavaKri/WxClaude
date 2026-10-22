"""Conversion between wx key events and the shortcut notation of ``core.shortcuts``."""

import wx

from wxclaude.core.config.shortcuts import normalize_shortcut

_NAMED_KEY_CODES = {
    wx.WXK_RETURN: "Enter",
    wx.WXK_NUMPAD_ENTER: "Enter",
    wx.WXK_SPACE: "Space",
    wx.WXK_TAB: "Tab",
    wx.WXK_ESCAPE: "Esc",
    wx.WXK_HOME: "Home",
    wx.WXK_END: "End",
    wx.WXK_PAGEUP: "PageUp",
    wx.WXK_PAGEDOWN: "PageDown",
    wx.WXK_UP: "Up",
    wx.WXK_DOWN: "Down",
    wx.WXK_LEFT: "Left",
    wx.WXK_RIGHT: "Right",
    wx.WXK_DELETE: "Delete",
    wx.WXK_INSERT: "Insert",
    wx.WXK_BACK: "Backspace",
}
_FUNCTION_KEY_CODES = {getattr(wx, f"WXK_F{number}"): f"F{number}" for number in range(1, 13)}


def key_name(code: int) -> str | None:
    """Name of the key with wx key ``code`` (``F2``, ``O``, ``PageUp``...), None if unsupported."""
    if code in _NAMED_KEY_CODES:
        return _NAMED_KEY_CODES[code]
    if code in _FUNCTION_KEY_CODES:
        return _FUNCTION_KEY_CODES[code]
    if ord("A") <= code <= ord("Z") or ord("0") <= code <= ord("9"):
        return chr(code)
    return None


def shortcut_from_event(event: wx.KeyEvent) -> str | None:
    """The shortcut pressed, e.g. ``Ctrl+Shift+O``; None for a modifier alone or an unknown key."""
    name = key_name(event.GetKeyCode())
    if name is None:
        return None
    parts = []
    if event.ControlDown():
        parts.append("Ctrl")
    if event.AltDown():
        parts.append("Alt")
    if event.ShiftDown():
        parts.append("Shift")
    return normalize_shortcut("+".join([*parts, name]))
