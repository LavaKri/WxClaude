"""The tab "Environment variables" of the Workspace settings: the view of
``presenters/env_vars_presenter.py``."""

import wx

from wxclaude.core.claude.claude_settings import ToolSettings
from wxclaude.core.labels import accessible_name
from wxclaude.i18n import _
from wxclaude.presenters.env_vars_presenter import EnvVarsPresenter
from wxclaude.ui.fields import read_only_field


class EnvVarsPage(wx.Panel):
    """The target file, the variables with their state, the buttons and the explanation of the
    selected variable. The controls are created in the order the Tab key visits them, each label
    right before its control so that screen readers pair them."""

    def __init__(self, parent: wx.Window, settings: ToolSettings, *, local_only: bool) -> None:
        super().__init__(parent)
        self.presenter: EnvVarsPresenter  # made once the controls exist
        sizer = wx.BoxSizer(wx.VERTICAL)
        target_text = _("&Target file")
        sizer.Add(wx.StaticText(self, label=target_text), 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        self._target = wx.Choice(self, name=accessible_name(target_text))
        self._target.Bind(wx.EVT_CHOICE, lambda _event: self.presenter.select_target(self._index))
        sizer.Add(self._target, 0, wx.EXPAND | wx.ALL, 8)

        list_text = _("&Variables")
        sizer.Add(wx.StaticText(self, label=list_text), 0, wx.LEFT | wx.RIGHT, 8)
        self._list = wx.ListBox(self, name=accessible_name(list_text))
        self._list.SetMinSize(wx.Size(-1, self._list.GetCharHeight() * 10 + 12))
        self._list.Bind(
            wx.EVT_LISTBOX, lambda _event: self.presenter.select(self._list.GetSelection())
        )
        sizer.Add(self._list, 1, wx.EXPAND | wx.ALL, 8)

        self._toggle = wx.Button(self, label=_("&Enable"))
        self._set = wx.Button(self, label=_("&Set the value..."))
        self._remove = wx.Button(self, label=_("Re&move"))
        self._toggle.Bind(wx.EVT_BUTTON, lambda _event: self.presenter.toggle())
        self._set.Bind(wx.EVT_BUTTON, lambda _event: self.presenter.set_value())
        self._remove.Bind(wx.EVT_BUTTON, lambda _event: self.presenter.remove())
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        for button in (self._toggle, self._set, self._remove):
            buttons.Add(button, 0, wx.RIGHT, 6)
        sizer.Add(buttons, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        explanation_text = _("E&xplanation")
        sizer.Add(wx.StaticText(self, label=explanation_text), 0, wx.LEFT | wx.RIGHT, 8)
        self._explanation = read_only_field(self, 4, name=accessible_name(explanation_text))
        sizer.Add(self._explanation, 0, wx.EXPAND | wx.ALL, 8)
        self.SetSizer(sizer)
        self.presenter = EnvVarsPresenter(self, settings, local_only=local_only)

    @property
    def _index(self) -> int:
        return int(self._target.GetSelection())

    # The view of the presenter ---------------------------------------------------------------

    def show_targets(self, labels: list[str], selected: int) -> None:
        self._target.Set(labels)
        self._target.SetSelection(selected)

    def show_rows(self, lines: list[str], selected: int) -> None:
        self._list.Set(lines)
        if selected >= 0:
            self._list.SetSelection(selected)

    def show_explanation(self, text: str) -> None:
        self._explanation.ChangeValue(text)

    def show_actions(self, toggle: str, can_toggle: bool, can_set: bool, can_remove: bool) -> None:
        self._toggle.SetLabel("&" + toggle)
        self._toggle.Enable(can_toggle)
        self._set.Enable(can_set)
        self._remove.Enable(can_remove)

    def ask_value(self, name: str, current: str) -> str | None:
        message = _("Value of {name}:").format(name=name)
        with wx.TextEntryDialog(self, message, _("Environment variable"), current) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return None
            return str(dialog.GetValue())

    def confirm_versioned(self) -> bool:
        message = _(
            "This file is versioned: the other developers of the project get this change. "
            "Change it anyway?"
        )
        style = wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING
        with wx.MessageDialog(self, message, _("Environment variables"), style) as dialog:
            return bool(dialog.ShowModal() == wx.ID_YES)

    def show_error(self, message: str) -> None:
        with wx.MessageDialog(
            self, message, _("Environment variables"), wx.OK | wx.ICON_ERROR
        ) as dialog:
            dialog.ShowModal()

    def focus_first(self) -> None:
        """The initial focus of the tab: the list of the variables."""
        self._list.SetFocus()
