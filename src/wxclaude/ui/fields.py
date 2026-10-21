"""Small helpers to build the controls that several dialogs need."""

import wx


def read_only_field(
    parent: wx.Window, lines: int, *, name: str = "", wrap: bool = True
) -> wx.TextCtrl:
    """A read-only text field that the Tab key still reaches (and a screen reader can read).

    wx does not give the keyboard focus to a read-only *single-line* text control, so the field
    is a multi-line one, sized for ``lines`` lines. Without ``wrap`` each line stays on one line.
    """
    style = wx.TE_READONLY | wx.TE_MULTILINE
    if not wrap:
        style |= wx.HSCROLL
    field = (
        wx.TextCtrl(parent, style=style, name=name) if name else wx.TextCtrl(parent, style=style)
    )
    field.SetMinSize(wx.Size(-1, field.GetCharHeight() * lines + 10))
    return field
