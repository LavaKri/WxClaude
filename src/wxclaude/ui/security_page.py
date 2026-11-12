"""The tab "Security" of the Workspace settings: the view of
``presenters/security_tab_presenter.py``."""

from pathlib import Path

import wx

from wxclaude.core.labels import accessible_name
from wxclaude.i18n import _
from wxclaude.presenters.security_presenter import SecurityPresenter
from wxclaude.presenters.security_tab_presenter import SecurityTabPresenter
from wxclaude.ui.fields import read_only_field


class SecurityPage(wx.Panel):
    """The check box *Trusted folder*, the watched files each with a check box, the buttons and the
    text that explains the restricted mode. What is decided here applies at once."""

    def __init__(self, parent: wx.Window, security: SecurityPresenter, workspace: Path) -> None:
        super().__init__(parent)
        self.presenter: SecurityTabPresenter  # made once the controls exist
        sizer = wx.BoxSizer(wx.VERTICAL)
        self._trusted = wx.CheckBox(self, label=_("&Trusted folder"))
        self._trusted.Bind(
            wx.EVT_CHECKBOX, lambda _event: self.presenter.set_trusted(self._trusted.GetValue())
        )
        sizer.Add(self._trusted, 0, wx.ALL, 8)

        turns_text = _("&Limit of turns per message (0: no limit)")
        turns_row = wx.BoxSizer(wx.HORIZONTAL)
        turns_row.Add(
            wx.StaticText(self, label=turns_text), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8
        )
        self._turns = wx.SpinCtrl(self, min=0, max=1000, name=accessible_name(turns_text))
        self._turns.Bind(
            wx.EVT_SPINCTRL, lambda _event: self.presenter.set_max_turns(self._turns.GetValue())
        )
        turns_row.Add(self._turns, 0)
        sizer.Add(turns_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        files_text = _("&Watched files")
        sizer.Add(wx.StaticText(self, label=files_text), 0, wx.LEFT | wx.RIGHT, 8)
        self._files = wx.CheckListBox(self, name=accessible_name(files_text))
        self._files.SetMinSize(wx.Size(-1, self._files.GetCharHeight() * 9 + 12))
        self._files.Bind(
            wx.EVT_LISTBOX, lambda _event: self.presenter.select(self._files.GetSelection())
        )
        self._files.Bind(wx.EVT_CHECKLISTBOX, self._on_check)
        sizer.Add(self._files, 1, wx.EXPAND | wx.ALL, 8)

        self._accept = wx.Button(self, label=_("&Accept the change"))
        self._add = wx.Button(self, label=_("Add a &file..."))
        self._forget = wx.Button(self, label=_("Re&move from the list"))
        self._accept.Bind(wx.EVT_BUTTON, lambda _event: self.presenter.accept())
        self._add.Bind(wx.EVT_BUTTON, lambda _event: self.presenter.add_file())
        self._forget.Bind(wx.EVT_BUTTON, lambda _event: self.presenter.forget())
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        for button in (self._accept, self._add, self._forget):
            buttons.Add(button, 0, wx.RIGHT, 6)
        sizer.Add(buttons, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        text = _("E&xplanation")
        sizer.Add(wx.StaticText(self, label=text), 0, wx.LEFT | wx.RIGHT, 8)
        self._explanation = read_only_field(self, 7, name=accessible_name(text))
        sizer.Add(self._explanation, 0, wx.EXPAND | wx.ALL, 8)
        self.SetSizer(sizer)
        self.presenter = SecurityTabPresenter(self, security, workspace)

    def _on_check(self, event: wx.CommandEvent) -> None:
        index = event.GetInt()
        self.presenter.set_watched(index, bool(self._files.IsChecked(index)))

    # The view of the presenter ---------------------------------------------------------------

    def show_trusted(self, trusted: bool) -> None:
        self._trusted.SetValue(trusted)

    def show_max_turns(self, turns: int) -> None:
        self._turns.SetValue(turns)

    def show_files(self, lines: list[str], watched: list[bool], selected: int) -> None:
        self._files.Set(lines)
        for index, checked in enumerate(watched):
            self._files.Check(index, checked)
        if selected >= 0:
            self._files.SetSelection(selected)

    def show_explanation(self, text: str) -> None:
        self._explanation.ChangeValue(text)

    def show_actions(self, can_accept: bool, can_forget: bool) -> None:
        self._accept.Enable(can_accept)
        self._forget.Enable(can_forget)

    def confirm_approval(self) -> bool:
        message = _(
            "Approve this folder? Claude will use its hooks, its settings and its servers, which "
            "can run commands on your computer. Approve only a folder you trust."
        )
        style = wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING
        with wx.MessageDialog(self, message, _("Trusted folder"), style) as dialog:
            dialog.SetYesNoLabels(_("&Approve the folder"), _("&Keep restricted"))
            return bool(dialog.ShowModal() == wx.ID_YES)

    def ask_file(self, folder: Path) -> Path | None:
        with wx.FileDialog(
            self, _("Choose a file to watch"), defaultDir=str(folder), style=wx.FD_OPEN
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return None
            return Path(dialog.GetPath())

    def show_error(self, message: str) -> None:
        with wx.MessageDialog(self, message, _("Security"), wx.OK | wx.ICON_ERROR) as dialog:
            dialog.ShowModal()

    def focus_first(self) -> None:
        """The initial focus of the tab: the check box *Trusted folder*."""
        self._trusted.SetFocus()
