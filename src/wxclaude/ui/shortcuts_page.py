"""A page to choose the keyboard shortcuts of a list of commands.

The page knows nothing of the settings of the application: it receives the commands and their
current shortcuts, and gives the chosen shortcuts back (``shortcuts``). It can be copied with
``core/shortcuts.py``, ``ui/shortcut_keys.py`` and ``ui/fields.py``.
"""

from collections.abc import Mapping, Sequence

import wx

from wxclaude.core.shortcuts import (
    ConfigurableCommand,
    ShortcutCheck,
    ShortcutProblem,
    check_shortcut,
)
from wxclaude.i18n import _
from wxclaude.ui.fields import read_only_field
from wxclaude.ui.shortcut_keys import shortcut_from_event


def shortcut_problem_message(check: ShortcutCheck, shortcut: str) -> str:
    """Explain why ``shortcut`` was refused."""
    if check.problem is ShortcutProblem.TAKEN and check.other is not None:
        return _('{shortcut} is already used by the command "{command}".').format(
            shortcut=shortcut, command=_(check.other.label)
        )
    if check.problem is ShortcutProblem.FIXED:
        return _("{shortcut} is the shortcut of a standard command and cannot be reused.").format(
            shortcut=shortcut
        )
    if check.problem is ShortcutProblem.RESERVED:
        return _(
            "{shortcut} cannot be used: a shortcut needs the Ctrl key, the Alt key or both "
            "(or be a function key), Enter needs at least one modifier key, and Tab, Esc and "
            "Insert are reserved for navigation and screen readers."
        ).format(shortcut=shortcut)
    return _("{shortcut} is not a valid shortcut.").format(shortcut=shortcut)


class ShortcutsPage(wx.Panel):
    """The list of the commands, a field to press the new shortcut, and two buttons."""

    def __init__(
        self,
        parent: wx.Window,
        commands: Sequence[ConfigurableCommand],
        shortcuts: Mapping[str, str],
    ) -> None:
        super().__init__(parent)
        self._commands = list(commands)
        self._shortcuts = dict(shortcuts)
        list_label = wx.StaticText(self, label=_("Shortcut &list:"))
        self.command_list = wx.ListCtrl(
            self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL, name=_("Shortcut list")
        )
        self.command_list.AppendColumn(_("Command"), width=330)
        self.command_list.AppendColumn(_("Shortcut"), width=200)
        for command in self._commands:
            self.command_list.Append((_(command.label), ""))
        capture_label = wx.StaticText(self, label=_("Press the new &shortcut here:"))
        self.capture = read_only_field(self, 2)
        self.default_button = wx.Button(self, label=_("Restore the &default shortcut"))
        self.clear_button = wx.Button(self, label=_("&No shortcut"))

        self.command_list.Bind(wx.EVT_LIST_ITEM_SELECTED, lambda _event: self._show_current())
        self.capture.Bind(wx.EVT_KEY_DOWN, self._on_capture_key)
        self.default_button.Bind(wx.EVT_BUTTON, lambda _event: self.restore_default())
        self.clear_button.Bind(wx.EVT_BUTTON, lambda _event: self.clear_shortcut())

        buttons = wx.BoxSizer(wx.HORIZONTAL)
        buttons.Add(self.default_button, 0, wx.RIGHT, 8)
        buttons.Add(self.clear_button)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(list_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        sizer.Add(self.command_list, 1, wx.EXPAND | wx.ALL, 8)
        sizer.Add(capture_label, 0, wx.LEFT | wx.RIGHT, 8)
        sizer.Add(self.capture, 0, wx.EXPAND | wx.ALL, 8)
        sizer.Add(buttons, 0, wx.ALL, 8)
        self.SetSizer(sizer)
        self._refresh_list()
        self.command_list.Select(0)

    @property
    def shortcuts(self) -> dict[str, str]:
        """The shortcut chosen for each command, by command id (empty: none)."""
        return dict(self._shortcuts)

    def selected_command(self) -> ConfigurableCommand | None:
        """The command selected in the list."""
        index = self.command_list.GetFirstSelected()
        return self._commands[index] if index >= 0 else None

    def assign_shortcut(self, command: ConfigurableCommand, shortcut: str) -> ShortcutCheck:
        """Give ``shortcut`` to ``command`` unless a rule refuses it; return the verdict."""
        check = check_shortcut(command, shortcut, self._shortcuts)
        if check.problem is None:
            self._shortcuts[command.id] = shortcut
            self._refresh_list()
            self._show_current()
        return check

    def restore_default(self) -> None:
        """Back to the default shortcut of the selected command."""
        command = self.selected_command()
        if command is not None:
            self.assign_shortcut(command, command.default)

    def clear_shortcut(self) -> None:
        """Remove the shortcut of the selected command."""
        command = self.selected_command()
        if command is not None:
            self.assign_shortcut(command, "")

    def _shortcut_text(self, command: ConfigurableCommand) -> str:
        return self._shortcuts[command.id] or _("None")

    def _refresh_list(self) -> None:
        for index, command in enumerate(self._commands):
            self.command_list.SetItem(index, 1, self._shortcut_text(command))

    def _show_current(self) -> None:
        command = self.selected_command()
        self.capture.SetValue(self._shortcut_text(command) if command else "")

    def _on_capture_key(self, event: wx.KeyEvent) -> None:
        if event.GetKeyCode() == wx.WXK_TAB and not event.ControlDown() and not event.AltDown():
            # Tab and Shift+Tab must always let the user leave the field.
            flags = (
                wx.NavigationKeyEvent.IsBackward
                if event.ShiftDown()
                else wx.NavigationKeyEvent.IsForward
            )
            self.capture.Navigate(flags)
            return
        command = self.selected_command()
        shortcut = shortcut_from_event(event)
        if command is None or shortcut is None:
            event.Skip()  # a modifier on its own, or a key that cannot be a shortcut
            return
        check = self.assign_shortcut(command, shortcut)
        if check.problem is not None:
            with wx.MessageDialog(
                self,
                shortcut_problem_message(check, shortcut),
                _("Options"),
                wx.OK | wx.ICON_WARNING,
            ) as dialog:
                dialog.ShowModal()
            self._show_current()
