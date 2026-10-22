"""Preferences dialog: a notebook with one page per topic (the pages are in their own modules)."""

import wx

from wxclaude.core.config.settings import Settings
from wxclaude.core.config.shortcuts import CONFIGURABLE_COMMANDS
from wxclaude.i18n import _
from wxclaude.ui.preferences_pages import (
    AgentPage,
    ClaudePage,
    GeneralPage,
    PreferencesPage,
    ScreenReaderPage,
    WorkspacePage,
)
from wxclaude.ui.shortcuts_page import ShortcutsPage


class PreferencesDialog(wx.Dialog):
    """Edit the preferences. ``apply`` copies the chosen values into the settings."""

    def __init__(self, parent: wx.Window, settings: Settings) -> None:
        super().__init__(
            parent, title=_("Preferences"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        self._notebook = wx.Notebook(self, name=_("Preferences"))
        self.general = GeneralPage(self._notebook, settings)
        self.claude = ClaudePage(self._notebook, settings)
        self.workspace = WorkspacePage(self._notebook, settings)
        self.agent = AgentPage(self._notebook, settings)
        self.shortcuts = ShortcutsPage(
            self._notebook, CONFIGURABLE_COMMANDS, settings.all_shortcuts()
        )
        self.screen_reader = ScreenReaderPage(self._notebook, settings)
        self._pages: list[PreferencesPage] = [
            self.general,
            self.claude,
            self.workspace,
            self.agent,
            self.screen_reader,
        ]
        self._notebook.AddPage(self.general, _("General"))
        self._notebook.AddPage(self.claude, _("Claude"))
        self._notebook.AddPage(self.workspace, _("Workspace"))
        self._notebook.AddPage(self.agent, _("Agent"))
        self._notebook.AddPage(self.shortcuts, _("Shortcuts"))
        self._notebook.AddPage(self.screen_reader, _("Screen reader"))

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self._notebook, 1, wx.EXPAND | wx.ALL, 6)
        sizer.Add(self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL), 0, wx.EXPAND | wx.ALL, 6)
        self.SetSizerAndFit(sizer)
        self.SetSize(wx.Size(720, 640))
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)
        self._notebook.SetFocus()

    def _on_ok(self, event: wx.CommandEvent) -> None:
        """Refuse OK when a page has a problem: show its page, put the focus on it and say why."""
        for page in self._pages:
            problem = page.validate()
            if problem is not None:
                self._notebook.SetSelection(self._notebook.FindPage(page))
                problem.control.SetFocus()
                with wx.MessageDialog(
                    self, problem.message, _("Preferences"), wx.OK | wx.ICON_WARNING
                ) as dialog:
                    dialog.ShowModal()
                return
        event.Skip()

    def apply(self, settings: Settings) -> None:
        """Store the values chosen in the dialog into ``settings``."""
        for page in self._pages:
            page.apply(settings)
        chosen = self.shortcuts.shortcuts
        for command in CONFIGURABLE_COMMANDS:
            settings.set_shortcut(command, chosen[command.id])
