"""A dialog with a read-only text field and a Close button: a report, a list of names."""

from collections.abc import Sequence

import wx

from wxclaude.core.labels import accessible_name


class TextDialog(wx.Dialog):
    """A read-only field with one fact per line. It has the initial focus, so a screen reader
    reads the text at once. ``label`` is the visible text of the field, with its access key. With
    ``caret_at_end`` the caret is on the last line (a history, whose newest line is the last)."""

    def __init__(
        self,
        parent: wx.Window,
        title: str,
        label: str,
        lines: Sequence[str],
        *,
        caret_at_end: bool = False,
    ) -> None:
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE)
        caption = wx.StaticText(self, label=label)
        self._text = wx.TextCtrl(
            self,
            value="\n".join(lines),
            style=wx.TE_READONLY | wx.TE_MULTILINE,
            name=accessible_name(label),
        )
        self._text.SetMinSize(
            wx.Size(self._text.GetCharWidth() * 80, self._text.GetCharHeight() * 10)
        )

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(caption, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        sizer.Add(self._text, 1, wx.EXPAND | wx.ALL, 8)
        sizer.Add(self.CreateStdDialogButtonSizer(wx.CLOSE), 0, wx.EXPAND | wx.ALL, 8)
        self.SetSizerAndFit(sizer)
        self.SetEscapeId(wx.ID_CLOSE)
        self.Bind(wx.EVT_BUTTON, lambda _event: self.EndModal(wx.ID_CLOSE), id=wx.ID_CLOSE)
        self._text.SetFocus()
        if caret_at_end:
            self._text.SetInsertionPointEnd()
            # A Windows edit control selects its whole text when the dialog gives it the focus
            # for real: put the caret back on the last line once that has happened.
            self._text.Bind(wx.EVT_SET_FOCUS, self._on_first_focus)
            wx.CallAfter(self._caret_to_end)

    def _on_first_focus(self, event: wx.FocusEvent) -> None:
        event.Skip()
        self._text.Unbind(wx.EVT_SET_FOCUS)
        wx.CallAfter(self._caret_to_end)

    def _caret_to_end(self) -> None:
        if self:  # the dialog may already be gone
            self._text.SetInsertionPointEnd()
            self._text.ShowPosition(self._text.GetLastPosition())

    @property
    def text(self) -> str:
        return str(self._text.GetValue())
