"""Dialog to search the conversation."""

import wx

from wxclaude.core.conversation.search import SearchOptions
from wxclaude.core.labels import accessible_name
from wxclaude.i18n import _


class SearchDialog(wx.Dialog):
    """The term (selected so that typing replaces it) and the two options."""

    def __init__(self, parent: wx.Window, options: SearchOptions | None = None) -> None:
        super().__init__(parent, title=_("Find in the conversation"))
        previous = options or SearchOptions("")
        # The label is created right before its field so that screen readers pair them.
        text = _("&Search for")
        label = wx.StaticText(self, label=text)
        self._term = wx.TextCtrl(self, value=previous.term, name=accessible_name(text))
        self._term.SetMinSize(wx.Size(self._term.GetCharWidth() * 40, -1))
        self._match_case = wx.CheckBox(self, label=_("Match &case"))
        self._match_case.SetValue(previous.match_case)
        self._whole_word = wx.CheckBox(self, label=_("&Whole words only"))
        self._whole_word.SetValue(previous.whole_word)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        sizer.Add(self._term, 0, wx.EXPAND | wx.ALL, 8)
        sizer.Add(self._match_case, 0, wx.LEFT | wx.RIGHT, 8)
        sizer.Add(self._whole_word, 0, wx.ALL, 8)
        sizer.Add(self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL), 0, wx.EXPAND | wx.ALL, 8)
        self.SetSizerAndFit(sizer)
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)
        self._term.SetFocus()
        self._term.SelectAll()

    @property
    def options(self) -> SearchOptions:
        """What the user asked for."""
        return SearchOptions(
            str(self._term.GetValue()),
            self._match_case.GetValue(),
            self._whole_word.GetValue(),
        )

    def _on_ok(self, event: wx.CommandEvent) -> None:
        if self.options.term:
            event.Skip()  # lets the dialog close with wx.ID_OK
            return
        with wx.MessageDialog(
            self,
            _("The text to search for cannot be empty."),
            self.GetTitle(),
            wx.OK | wx.ICON_WARNING,
        ) as dialog:
            dialog.ShowModal()
        self._term.SetFocus()
