"""The settings of a workspace that Claude Code keeps in its ``.claude`` folder."""

from pathlib import Path

import wx

from wxclaude.core.claude_settings import (
    Approval,
    Rule,
    Source,
    ToolSettings,
    approval_label,
)
from wxclaude.core.errors import ClaudeSettingsError
from wxclaude.i18n import _


def _read_only_field(parent: wx.Window, lines: int, name: str) -> wx.TextCtrl:
    """A read-only multi-line field: the Tab key reaches it and a screen reader reads it."""
    field = wx.TextCtrl(parent, style=wx.TE_READONLY | wx.TE_MULTILINE, name=name)
    field.SetMinSize(wx.Size(-1, field.GetCharHeight() * lines + 10))
    return field


class WorkspaceSettingsDialog(wx.Dialog):
    """Edit the permission rules of the workspace; the caller saves ``tool_settings`` on OK.

    ``local_only`` limits the target file to the personal one (``settings.local.json``), so the
    versioned file shared with the other developers of the project is never modified.
    """

    def __init__(
        self,
        parent: wx.Window,
        tool_settings: ToolSettings,
        *,
        local_only: bool,
    ) -> None:
        super().__init__(
            parent,
            title=_("Workspace settings"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.tool_settings = tool_settings
        self._targets = [Source.LOCAL] if local_only else [Source.SETTINGS, Source.LOCAL]
        self._tool_names: list[str] = []
        self._rules: list[Rule] = []
        notebook = wx.Notebook(self, name=_("Workspace settings"))
        notebook.AddPage(self._tools_page(notebook), _("Tools"))

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(notebook, 1, wx.EXPAND | wx.ALL, 6)
        sizer.Add(self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL), 0, wx.EXPAND | wx.ALL, 6)
        self.SetSizerAndFit(sizer)
        self.SetSize(wx.Size(760, 700))
        self._refresh()
        self._tools.SetFocus()

    # Tools -----------------------------------------------------------------------------------

    def _tools_page(self, parent: wx.Window) -> wx.Panel:
        page = wx.Panel(parent)
        # Each label is created right before its control so that screen readers pair them.
        target_label = wx.StaticText(page, label=_("&Target file"))
        self._target = wx.Choice(
            page,
            choices=[self._target_name(source) for source in self._targets],
            name=_("Target file"),
        )
        self._target.SetSelection(0)
        self._target.Bind(wx.EVT_CHOICE, lambda _event: self._refresh())
        self._note = _read_only_field(page, 4, _("Where the changes are saved"))

        tools_label = wx.StaticText(page, label=_("&Tools"))
        self._tools = wx.ListBox(page, name=_("Tools"))
        self._tools.SetMinSize(wx.Size(-1, self._tools.GetCharHeight() * 8 + 12))
        self._tools.Bind(wx.EVT_LISTBOX, lambda _event: self._refresh_buttons())
        self._deny = wx.Button(page, label=_("De&ny"))
        self._ask = wx.Button(page, label=_("A&sk"))
        self._allow = wx.Button(page, label=_("&Allow"))
        self._deny.Bind(wx.EVT_BUTTON, lambda _event: self.apply_approval(Approval.DENY))
        self._ask.Bind(wx.EVT_BUTTON, lambda _event: self.apply_approval(Approval.ASK))
        self._allow.Bind(wx.EVT_BUTTON, lambda _event: self.apply_approval(Approval.ALLOW))

        rules_label = wx.StaticText(page, label=_("&Rules of the target file"))
        self._rules_list = wx.ListBox(page, name=_("Rules of the target file"))
        self._rules_list.SetMinSize(wx.Size(-1, self._rules_list.GetCharHeight() * 6 + 12))
        self._rules_list.Bind(wx.EVT_LISTBOX, lambda _event: self._refresh_buttons())
        self._remove = wx.Button(page, label=_("Re&move"))
        self._remove.Bind(wx.EVT_BUTTON, lambda _event: self.remove_selected_rule())

        new_label = wx.StaticText(page, label=_("Rule to a&dd"))
        self._new_rule = wx.TextCtrl(page, name=_("Rule to add"))
        approval_label_ = wx.StaticText(page, label=_("A&pproval of the rule"))
        self._new_approval = wx.Choice(
            page,
            choices=[approval_label(approval) for approval in Approval],
            name=_("Approval of the rule"),
        )
        self._new_approval.SetSelection(list(Approval).index(Approval.ALLOW))
        self._add = wx.Button(page, label=_("Add the ru&le"))
        self._add.Bind(wx.EVT_BUTTON, lambda _event: self._on_add())

        buttons = wx.BoxSizer(wx.HORIZONTAL)
        for button in (self._deny, self._ask, self._allow):
            buttons.Add(button, 0, wx.RIGHT, 6)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(target_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        sizer.Add(self._target, 0, wx.EXPAND | wx.ALL, 8)
        sizer.Add(self._note, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        sizer.Add(tools_label, 0, wx.LEFT | wx.RIGHT, 8)
        sizer.Add(self._tools, 1, wx.EXPAND | wx.ALL, 8)
        sizer.Add(buttons, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        sizer.Add(rules_label, 0, wx.LEFT | wx.RIGHT, 8)
        sizer.Add(self._rules_list, 1, wx.EXPAND | wx.ALL, 8)
        sizer.Add(self._remove, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        sizer.Add(new_label, 0, wx.LEFT | wx.RIGHT, 8)
        sizer.Add(self._new_rule, 0, wx.EXPAND | wx.ALL, 8)
        sizer.Add(approval_label_, 0, wx.LEFT | wx.RIGHT, 8)
        sizer.Add(self._new_approval, 0, wx.EXPAND | wx.ALL, 8)
        sizer.Add(self._add, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        page.SetSizer(sizer)
        return page

    @staticmethod
    def _target_name(source: Source) -> str:
        if source is Source.SETTINGS:
            return _("Settings (shared, versioned)")
        return _("SettingsLocal (personal, not versioned)")

    @property
    def target(self) -> Source:
        """The file the changes go to."""
        target: Source = self._targets[self._target.GetSelection()]
        return target

    def set_target(self, source: Source) -> None:
        """Choose the target file (it must be one of the proposed ones)."""
        self._target.SetSelection(self._targets.index(source))
        self._refresh()

    @property
    def selected_tool(self) -> str | None:
        index = self._tools.GetSelection()
        return self._tool_names[index] if index != wx.NOT_FOUND else None

    def select_tool(self, name: str) -> None:
        self._tools.SetSelection(self._tool_names.index(name))
        self._refresh_buttons()

    def select_rule(self, index: int) -> None:
        self._rules_list.SetSelection(index)
        self._refresh_buttons()

    # What the buttons do ---------------------------------------------------------------------

    def apply_approval(self, approval: Approval) -> None:
        """Give the selected tool one rule without specifier in the target file."""
        tool = self.selected_tool
        if tool is None:
            return
        try:
            self.tool_settings.set_approval(self.target, tool, approval)
        except ClaudeSettingsError as error:
            self._show_error(str(error))
            return
        self._refresh(keep_tool=tool)

    def remove_selected_rule(self) -> None:
        """Remove the selected rule from the target file."""
        index = self._rules_list.GetSelection()
        if index == wx.NOT_FOUND:
            return
        try:
            self.tool_settings.remove_rule(self.target, self._rules[index])
        except ClaudeSettingsError as error:
            self._show_error(str(error))
            return
        self._refresh(keep_tool=self.selected_tool, keep_rule=index)

    def add_rule(self, pattern: str, approval: Approval) -> bool:
        """Add a rule to the target file as typed; False if it is empty or cannot be written."""
        pattern = pattern.strip()
        if not pattern:
            return False
        try:
            self.tool_settings.add_rule(self.target, Rule(approval, pattern))
        except ClaudeSettingsError as error:
            self._show_error(str(error))
            return False
        self._refresh(keep_tool=self.selected_tool)
        return True

    def _on_add(self) -> None:
        approval = list(Approval)[self._new_approval.GetSelection()]
        if self.add_rule(str(self._new_rule.GetValue()), approval):
            self._new_rule.Clear()
        else:
            self._new_rule.SetFocus()

    # Showing the state -----------------------------------------------------------------------

    def _refresh(self, *, keep_tool: str | None = None, keep_rule: int | None = None) -> None:
        target = self.target
        self._tool_names = self.tool_settings.tools()
        self._tools.Set(
            [self.tool_settings.state(name, target).text(name) for name in self._tool_names]
        )
        if keep_tool in self._tool_names:
            self._tools.SetSelection(self._tool_names.index(str(keep_tool)))
        elif self._tool_names:
            self._tools.SetSelection(0)
        self._rules = self.tool_settings.rules(target)
        self._rules_list.Set([rule.text() for rule in self._rules])
        if self._rules:
            self._rules_list.SetSelection(min(keep_rule or 0, len(self._rules) - 1))
        self._note.SetValue(self._note_text(target))
        self._refresh_buttons()

    def _note_text(self, target: Source) -> str:
        file = self.tool_settings.files[target]
        if target is Source.SETTINGS:
            kind = _("This file is versioned: the other developers of the project get the changes.")
        else:
            kind = _("This file is personal and is not versioned.")
        lines = [_("The changes are saved in {path}.").format(path=file.path), kind]
        if file.error:
            lines.append(_("This file cannot be modified: {error}").format(error=file.error))
        general = self.tool_settings.files[Source.GENERAL]
        lines.append(_("The general file {path} is only read.").format(path=general.path))
        return "\n".join(lines)

    def _refresh_buttons(self) -> None:
        writable = self.tool_settings.files[self.target].writable
        has_tool = self._tools.GetSelection() != wx.NOT_FOUND
        for button in (self._deny, self._ask, self._allow):
            button.Enable(writable and has_tool)
        self._remove.Enable(writable and self._rules_list.GetSelection() != wx.NOT_FOUND)
        self._add.Enable(writable)

    def _show_error(self, message: str) -> None:
        with wx.MessageDialog(self, message, self.GetTitle(), wx.OK | wx.ICON_ERROR) as dialog:
            dialog.ShowModal()

    @property
    def target_path(self) -> Path:
        """The path of the target file, for tests and messages."""
        return self.tool_settings.files[self.target].path
