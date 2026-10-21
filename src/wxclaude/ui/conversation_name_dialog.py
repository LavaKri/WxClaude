"""Dialog to give a name to a conversation (new, renamed or branched)."""

import wx

from wxclaude.core.labels import accessible_name
from wxclaude.i18n import _


class ConversationNameDialog(wx.Dialog):
    """One field holding the proposed name, selected so that typing replaces it."""

    def __init__(self, parent: wx.Window, title: str, name: str) -> None:
        super().__init__(parent, title=title)
        # The label is created right before its field so that screen readers pair them.
        text = _("&Name")
        label = wx.StaticText(self, label=text)
        self._name = wx.TextCtrl(self, value=name, name=accessible_name(text))
        self._name.SetMinSize(wx.Size(self._name.GetCharWidth() * 40, -1))

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        sizer.Add(self._name, 0, wx.EXPAND | wx.ALL, 8)
        sizer.Add(self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL), 0, wx.EXPAND | wx.ALL, 8)
        self.SetSizerAndFit(sizer)
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)
        self._name.SetFocus()
        self._name.SelectAll()

    @property
    def name(self) -> str:
        """The name typed by the user, without the spaces around it."""
        return str(self._name.GetValue()).strip()

    def _on_ok(self, event: wx.CommandEvent) -> None:
        if self.name:
            event.Skip()  # lets the dialog close with wx.ID_OK
            return
        with wx.MessageDialog(
            self, _("The name cannot be empty."), self.GetTitle(), wx.OK | wx.ICON_WARNING
        ) as dialog:
            dialog.ShowModal()
        self._name.SetFocus()
