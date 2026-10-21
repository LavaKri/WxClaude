"""Dialog showing the usage of Claude: the subscription gauges and the tokens spent."""

from collections.abc import Sequence

import wx

from wxclaude.i18n import _


class UsageDialog(wx.Dialog):
    """A read-only field with one fact per line. It has the initial focus, so a screen reader
    reads the report at once."""

    def __init__(self, parent: wx.Window, lines: Sequence[str]) -> None:
        super().__init__(parent, title=_("Claude usage"), style=wx.DEFAULT_DIALOG_STYLE)
        label = wx.StaticText(self, label=_("&Usage"))
        self._report = wx.TextCtrl(
            self,
            value="\n".join(lines),
            style=wx.TE_READONLY | wx.TE_MULTILINE,
            name=_("Usage"),
        )
        self._report.SetMinSize(
            wx.Size(self._report.GetCharWidth() * 80, self._report.GetCharHeight() * 10)
        )

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        sizer.Add(self._report, 1, wx.EXPAND | wx.ALL, 8)
        sizer.Add(self.CreateStdDialogButtonSizer(wx.CLOSE), 0, wx.EXPAND | wx.ALL, 8)
        self.SetSizerAndFit(sizer)
        self.SetEscapeId(wx.ID_CLOSE)
        self.Bind(wx.EVT_BUTTON, lambda _event: self.EndModal(wx.ID_CLOSE), id=wx.ID_CLOSE)
        self._report.SetFocus()

    @property
    def report(self) -> str:
        return str(self._report.GetValue())
