"""Options dialog, one tab per topic."""

import wx

from wxclaude.core.screen_reader import available_outputs, default_output, output_named
from wxclaude.core.settings import SUPPORTED_LANGUAGES, Settings
from wxclaude.core.shortcuts import (
    CONFIGURABLE_COMMANDS,
    ConfigurableCommand,
    ShortcutCheck,
    ShortcutProblem,
    check_shortcut,
)
from wxclaude.i18n import _
from wxclaude.ui.agent_panel import AgentPanel, permission_levels_lines
from wxclaude.ui.shortcut_keys import shortcut_from_event

# Names of the languages, each in its own language (never translated).
_LANGUAGE_NAMES = {"fr": "Français", "en": "English"}


def _read_only_field(parent: wx.Window, lines: int, *, wrap: bool = True) -> wx.TextCtrl:
    """A read-only text field that the Tab key still reaches (and a screen reader can read).

    wx does not give the keyboard focus to a read-only *single-line* text control, so the field
    is a multi-line one, sized for ``lines`` lines.
    """
    style = wx.TE_READONLY | wx.TE_MULTILINE
    if not wrap:
        style |= wx.HSCROLL  # no wrapping: each line stays on one line
    field = wx.TextCtrl(parent, style=style)
    field.SetMinSize(wx.Size(-1, field.GetCharHeight() * lines + 10))
    return field


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


class OptionsDialog(wx.Dialog):
    """Edit the options. ``apply`` copies the chosen values into the settings."""

    def __init__(self, parent: wx.Window, settings: Settings) -> None:
        super().__init__(
            parent, title=_("Options"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        self._notebook = wx.Notebook(self, name=_("Options"))
        self._notebook.AddPage(self._general_page(settings), _("General"))
        self._notebook.AddPage(self._conversation_page(settings), _("Conversation"))
        self._notebook.AddPage(self._agent_page(settings), _("Agent"))
        self._notebook.AddPage(self._shortcuts_page(settings), _("Shortcuts"))
        self._notebook.AddPage(self._screen_reader_page(settings), _("Screen reader"))

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self._notebook, 1, wx.EXPAND | wx.ALL, 6)
        sizer.Add(self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL), 0, wx.EXPAND | wx.ALL, 6)
        self.SetSizerAndFit(sizer)
        self.SetSize(wx.Size(720, 640))
        self._notebook.SetFocus()

    # General ---------------------------------------------------------------------------------

    def _general_page(self, settings: Settings) -> wx.Panel:
        page = wx.Panel(self._notebook)
        # The label is created right before its control so that screen readers pair them.
        label = wx.StaticText(page, label=_("&Language"))
        self._language = wx.Choice(
            page,
            choices=[_LANGUAGE_NAMES[code] for code in SUPPORTED_LANGUAGES],
            name=_("Language"),
        )
        self._language.SetSelection(SUPPORTED_LANGUAGES.index(settings.language))
        note = wx.StaticText(page, label=_("The language change applies at the next start."))
        self._reopen_last = wx.CheckBox(page, label=_("At startup, &open the last workspace"))
        self._reopen_last.SetValue(settings.reopen_last)
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        row.Add(self._language, 0)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(row, 0, wx.ALL, 6)
        sizer.Add(note, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
        sizer.Add(self._reopen_last, 0, wx.ALL, 6)
        page.SetSizer(sizer)
        return page

    # Conversation ----------------------------------------------------------------------------

    def _conversation_page(self, settings: Settings) -> wx.Panel:
        page = wx.Panel(self._notebook)
        self._hide_system_messages = wx.CheckBox(page, label=_("&Hide the system messages"))
        self._hide_system_messages.SetValue(settings.hide_system_messages)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self._hide_system_messages, 0, wx.ALL, 6)
        page.SetSizer(sizer)
        return page

    # Agent -----------------------------------------------------------------------------------

    def _agent_page(self, settings: Settings) -> wx.Panel:
        page = wx.Panel(self._notebook)
        self._agents = [settings.default_agent, settings.alternative_agent]
        self._unset_labels = [None, _("(same as the conversation)")]
        self._agent_index = 0

        list_label = wx.StaticText(page, label=_("&Agent"))
        self._agent_list = wx.ListBox(
            page,
            choices=[_("Agent of a new conversation"), _("Alternative agent")],
            name=_("Agent"),
        )
        self._agent_list.SetMinSize(wx.Size(-1, self._agent_list.GetCharHeight() * 2 + 12))
        self._agent_list.SetSelection(0)
        self._agent_list.Bind(wx.EVT_LISTBOX, self._on_agent_chosen)
        self._agent_panel = AgentPanel(page, self._agents[0], self._unset_labels[0])

        levels_label = wx.StaticText(page, label=_("Implications of the permission &levels"))
        self._levels = _read_only_field(page, 8, wrap=False)
        self._levels.SetValue(
            "\n".join(permission_levels_lines())
            + "\n\n"
            + _(
                "Cache: when the alternative agent changes the model, the conversation cache is "
                "lost and the next message is slower and costs more."
            )
        )

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(list_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        sizer.Add(self._agent_list, 0, wx.EXPAND | wx.ALL, 8)
        sizer.Add(self._agent_panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 2)
        sizer.Add(levels_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        sizer.Add(self._levels, 1, wx.EXPAND | wx.ALL, 8)
        page.SetSizer(sizer)
        return page

    def _on_agent_chosen(self, _event: wx.CommandEvent) -> None:
        index = self._agent_list.GetSelection()
        if index < 0 or index == self._agent_index:
            return
        self._agents[self._agent_index] = self._agent_panel.agent
        self._agent_index = index
        self._agent_panel.set_agent(self._agents[index], self._unset_labels[index])

    # Shortcuts -------------------------------------------------------------------------------

    def _shortcuts_page(self, settings: Settings) -> wx.Panel:
        page = wx.Panel(self._notebook)
        self._shortcuts = settings.all_shortcuts()
        list_label = wx.StaticText(page, label=_("Shortcut &list:"))
        self.command_list = wx.ListCtrl(
            page, style=wx.LC_REPORT | wx.LC_SINGLE_SEL, name=_("Shortcut list")
        )
        self.command_list.AppendColumn(_("Command"), width=330)
        self.command_list.AppendColumn(_("Shortcut"), width=200)
        for command in CONFIGURABLE_COMMANDS:
            self.command_list.Append((_(command.label), ""))
        capture_label = wx.StaticText(page, label=_("Press the new &shortcut here:"))
        self.capture = _read_only_field(page, 2)
        self.default_button = wx.Button(page, label=_("Restore the &default shortcut"))
        self.clear_button = wx.Button(page, label=_("&No shortcut"))

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
        page.SetSizer(sizer)
        self._refresh_shortcut_list()
        self.command_list.Select(0)
        return page

    def selected_command(self) -> ConfigurableCommand | None:
        """The command selected in the Shortcuts list."""
        index = self.command_list.GetFirstSelected()
        return CONFIGURABLE_COMMANDS[index] if index >= 0 else None

    def _shortcut_text(self, command: ConfigurableCommand) -> str:
        return self._shortcuts[command.id] or _("None")

    def _refresh_shortcut_list(self) -> None:
        for index, command in enumerate(CONFIGURABLE_COMMANDS):
            self.command_list.SetItem(index, 1, self._shortcut_text(command))

    def _show_current(self) -> None:
        command = self.selected_command()
        self.capture.SetValue(self._shortcut_text(command) if command else "")

    def assign_shortcut(self, command: ConfigurableCommand, shortcut: str) -> ShortcutCheck:
        """Give ``shortcut`` to ``command`` unless a rule refuses it; return the verdict."""
        check = check_shortcut(command, shortcut, self._shortcuts)
        if check.problem is None:
            self._shortcuts[command.id] = shortcut
            self._refresh_shortcut_list()
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

    # Screen reader ---------------------------------------------------------------------------

    def _screen_reader_page(self, settings: Settings) -> wx.Panel:
        page = wx.Panel(self._notebook)
        self._outputs = available_outputs()
        label = wx.StaticText(page, label=_("&Announcements"))
        self.output_choice = wx.Choice(
            page, choices=[_(output.label) for output in self._outputs], name=_("Announcements")
        )
        current = output_named(settings.screen_reader_output) or default_output()
        self.output_choice.SetSelection(self._outputs.index(current))
        self._announce_progress = wx.CheckBox(page, label=_("Announce the &progress of Claude"))
        self._announce_progress.SetValue(settings.announce_progress)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        sizer.Add(self.output_choice, 0, wx.EXPAND | wx.ALL, 8)
        sizer.Add(self._announce_progress, 0, wx.ALL, 8)
        page.SetSizer(sizer)
        return page

    # OK --------------------------------------------------------------------------------------

    def apply(self, settings: Settings) -> None:
        """Store the values chosen in the dialog into ``settings``."""
        settings.language = SUPPORTED_LANGUAGES[self._language.GetSelection()]
        settings.reopen_last = self._reopen_last.GetValue()
        settings.hide_system_messages = self._hide_system_messages.GetValue()
        settings.announce_progress = self._announce_progress.GetValue()
        self._agents[self._agent_index] = self._agent_panel.agent
        settings.default_agent, settings.alternative_agent = self._agents
        for command in CONFIGURABLE_COMMANDS:
            settings.set_shortcut(command, self._shortcuts[command.id])
        settings.screen_reader_output = self._outputs[self.output_choice.GetSelection()].id
