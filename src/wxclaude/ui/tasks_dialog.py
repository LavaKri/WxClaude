"""Dialog showing the task list of the current conversation."""

import wx

from wxclaude.i18n import _


class TasksDialog(wx.Dialog):
    """Read-only list of tasks. Claude's tasks are not collected yet, so it is empty for now."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent, title=_("Task list"))
        label = wx.StaticText(self, label=_("&Tasks"))
        # A read-only multi-line field: the Tab key reaches it and a screen reader can read it.
        self._tasks = wx.TextCtrl(
            self, style=wx.TE_READONLY | wx.TE_MULTILINE, name=_("Tasks"), size=wx.Size(480, 160)
        )
        self._tasks.SetValue(_("No task in this conversation yet."))

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        sizer.Add(self._tasks, 1, wx.EXPAND | wx.ALL, 8)
        sizer.Add(self.CreateStdDialogButtonSizer(wx.CLOSE), 0, wx.EXPAND | wx.ALL, 8)
        self.SetSizerAndFit(sizer)
        self.SetEscapeId(wx.ID_CLOSE)
        self.Bind(wx.EVT_BUTTON, lambda _event: self.EndModal(wx.ID_CLOSE), id=wx.ID_CLOSE)
        self._tasks.SetFocus()
