"""Main window: conversation view, prompt field, send buttons and menus."""

from pathlib import Path

import wx

from wxclaude import __version__
from wxclaude.core.agents import Agent
from wxclaude.core.errors import ExportError, SettingsError
from wxclaude.core.export import export_text
from wxclaude.core.settings import Settings
from wxclaude.core.workspaces import add_recent, describe, remove_missing
from wxclaude.i18n import _
from wxclaude.ui.agent_dialog import AgentDialog
from wxclaude.ui.options_dialog import OptionsDialog


class MainWindow(wx.Frame):
    """Top-level window. Skeleton: Claude is not launched yet, sending only echoes the prompt."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(None, title=_("WxClaude"), size=wx.Size(900, 650))
        self._settings = settings
        self._workspace: Path | None = None
        self._agent = settings.default_agent
        self._busy = False  # True while Claude is answering (set by the runner, later)
        self._recent_ids: dict[int, str] = {}

        panel = wx.Panel(self)
        conversation_label = wx.StaticText(panel, label=_("Con&versation"))
        self._conversation = wx.TextCtrl(
            panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            name=_("Conversation"),
        )
        prompt_label = wx.StaticText(panel, label=_("&Prompt"))
        self._prompt = wx.TextCtrl(panel, style=wx.TE_MULTILINE, name=_("Prompt"))
        self._prompt.Bind(wx.EVT_KEY_DOWN, self._on_prompt_key)

        self._send_button = wx.Button(panel, label=_("&Send (Ctrl+Enter)"))
        self._alternative_button = wx.Button(
            panel, label=_("Send with the &alternative agent (Shift+Enter)")
        )
        self._interrupt_button = wx.Button(panel, label=_("&Interrupt Claude"))
        self._send_button.Bind(wx.EVT_BUTTON, lambda _event: self.send_prompt(alternative=False))
        self._alternative_button.Bind(
            wx.EVT_BUTTON, lambda _event: self.send_prompt(alternative=True)
        )
        self._send_button.Bind(wx.EVT_UPDATE_UI, self._on_update_send)
        self._alternative_button.Bind(wx.EVT_UPDATE_UI, self._on_update_send)
        self._interrupt_button.Bind(wx.EVT_UPDATE_UI, self._on_update_interrupt)

        buttons = wx.BoxSizer(wx.HORIZONTAL)
        buttons.Add(self._send_button, 0, wx.RIGHT, 6)
        buttons.Add(self._alternative_button, 0, wx.RIGHT, 6)
        buttons.Add(self._interrupt_button, 0)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(conversation_label, 0, wx.LEFT | wx.TOP, 6)
        sizer.Add(self._conversation, 3, wx.EXPAND | wx.ALL, 6)
        sizer.Add(prompt_label, 0, wx.LEFT, 6)
        sizer.Add(self._prompt, 1, wx.EXPAND | wx.ALL, 6)
        sizer.Add(buttons, 0, wx.ALL, 6)
        panel.SetSizer(sizer)

        self._build_menu_bar()
        self.CreateStatusBar()
        self.SetStatusText(_("Ready"))
        self.Bind(wx.EVT_MENU_OPEN, self._on_menu_open)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        wx.CallAfter(self._prompt.SetFocus)

    # Menus -----------------------------------------------------------------------------------

    def _build_menu_bar(self) -> None:
        self._file_menu = wx.Menu()
        open_item = self._file_menu.Append(wx.ID_ANY, _("&Open workspace…\tCtrl+O"))
        projects_item = self._file_menu.Append(wx.ID_ANY, _("Open from Claude &projects…"))
        projects_item.Enable(False)  # needs the Claude history reader (later milestone)
        self._recent_menu = wx.Menu()
        self._recent_item = self._file_menu.AppendSubMenu(self._recent_menu, _("&Recent"))
        export_item = self._file_menu.Append(wx.ID_ANY, _("&Export the conversation…"))
        self._file_menu.AppendSeparator()
        quit_item = self._file_menu.Append(wx.ID_EXIT, _("&Quit\tCtrl+Q"))

        conversation_menu = wx.Menu()
        new_item = conversation_menu.Append(wx.ID_ANY, _("&New conversation\tCtrl+N"))
        resume_item = conversation_menu.Append(
            wx.ID_ANY, _("&Resume a conversation…\tCtrl+Shift+O")
        )
        rename_item = conversation_menu.Append(wx.ID_ANY, _("Ren&ame the conversation"))
        branch_item = conversation_menu.Append(wx.ID_ANY, _("New conversation &branch"))
        delete_item = conversation_menu.Append(wx.ID_ANY, _("&Delete the conversation"))
        self._interrupt_item = conversation_menu.Append(
            wx.ID_ANY, _("&Interrupt Claude\tCtrl+Shift+I")
        )
        agent_item = conversation_menu.Append(wx.ID_ANY, _("&Modify the agent…"))
        # These need the session history and the Claude runner (later milestones).
        for pending in (resume_item, rename_item, branch_item, delete_item):
            pending.Enable(False)

        tools_menu = wx.Menu()
        options_item = tools_menu.Append(wx.ID_ANY, _("&Options…"))

        help_menu = wx.Menu()
        about_item = help_menu.Append(wx.ID_ABOUT, _("&About"))

        menu_bar = wx.MenuBar()
        menu_bar.Append(self._file_menu, _("&File"))
        menu_bar.Append(conversation_menu, _("&Conversation"))
        menu_bar.Append(tools_menu, _("&Tools"))
        menu_bar.Append(help_menu, _("&Help"))
        self.SetMenuBar(menu_bar)

        self.Bind(wx.EVT_MENU, self._on_open_workspace, open_item)
        self.Bind(wx.EVT_MENU, self._on_export, export_item)
        self.Bind(wx.EVT_MENU, lambda _event: self.Close(), quit_item)
        self.Bind(wx.EVT_MENU, self._on_new_conversation, new_item)
        self.Bind(wx.EVT_MENU, self._on_choose_agent, agent_item)
        self.Bind(wx.EVT_MENU, self._on_options, options_item)
        self.Bind(wx.EVT_MENU, self._on_about, about_item)
        self.Bind(wx.EVT_UPDATE_UI, self._on_update_interrupt, self._interrupt_item)

    def _on_menu_open(self, event: wx.MenuEvent) -> None:
        if event.GetMenu() is self._file_menu:
            self._refresh_recent_menu()
        event.Skip()

    def _refresh_recent_menu(self) -> None:
        """Rebuild the recent workspaces, dropping the folders that no longer exist."""
        self._settings.recent_workspaces = remove_missing(self._settings.recent_workspaces)
        for item in list(self._recent_menu.GetMenuItems()):
            self._recent_menu.Delete(item)
        self._recent_ids.clear()
        for folder in self._settings.recent_workspaces:
            name, parent = describe(folder)
            text = _("{name}, from {parent}").format(name=name, parent=parent) if parent else name
            item = self._recent_menu.Append(wx.ID_ANY, text.replace("&", "&&"))
            self._recent_ids[item.GetId()] = folder
            self.Bind(wx.EVT_MENU, self._on_recent, item)
        self._recent_item.Enable(bool(self._recent_ids))

    # Workspaces ------------------------------------------------------------------------------

    def open_workspace(self, folder: Path) -> None:
        """Make ``folder`` the working folder and remember it in the recent list."""
        self._workspace = folder
        self._settings.recent_workspaces = add_recent(self._settings.recent_workspaces, folder)
        name, _parent = describe(str(folder))
        self.SetTitle(_("{folder} - WxClaude").format(folder=name))
        self.SetStatusText(_("Workspace: {folder}").format(folder=folder))
        self._save_settings()

    def _on_open_workspace(self, _event: wx.CommandEvent) -> None:
        default = str(self._workspace) if self._workspace else ""
        with wx.DirDialog(
            self,
            _("Choose the working folder"),
            defaultPath=default,
            style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST,
        ) as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                self.open_workspace(Path(dialog.GetPath()))

    def _on_recent(self, event: wx.CommandEvent) -> None:
        folder = self._recent_ids.get(event.GetId())
        if folder is None:
            return
        if Path(folder).is_dir():
            self.open_workspace(Path(folder))
            return
        self._settings.recent_workspaces = remove_missing(self._settings.recent_workspaces)
        self._show_error(
            _("The folder {folder} no longer exists. It was removed from the recent list.").format(
                folder=folder
            )
        )

    # Conversation ----------------------------------------------------------------------------

    def _on_new_conversation(self, _event: wx.CommandEvent) -> None:
        self._conversation.Clear()
        self._prompt.Clear()
        self._agent = self._settings.default_agent
        self.SetStatusText(_("New conversation."))
        self._prompt.SetFocus()

    def _on_export(self, _event: wx.CommandEvent) -> None:
        with wx.FileDialog(
            self,
            _("Export the conversation"),
            defaultFile=_("conversation.txt"),
            wildcard=_("Text files (*.txt)|*.txt|Markdown files (*.md)|*.md"),
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            path = Path(dialog.GetPath())
        try:
            export_text(path, self._conversation.GetValue())
        except ExportError as error:
            self._show_error(_("Cannot export the conversation.\n{error}").format(error=error))
            return
        self.SetStatusText(_("Conversation exported to {path}.").format(path=path))

    def _on_choose_agent(self, _event: wx.CommandEvent) -> None:
        with AgentDialog(self, self._agent) as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                self._agent = dialog.agent
                self.SetStatusText(_("Agent updated."))

    def _on_options(self, _event: wx.CommandEvent) -> None:
        with OptionsDialog(self, self._settings) as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                dialog.apply(self._settings)
                self._save_settings()

    def _on_about(self, _event: wx.CommandEvent) -> None:
        message = _("WxClaude {version}").format(version=__version__)
        wx.MessageBox(message, _("About"), wx.OK | wx.ICON_INFORMATION, self)

    # Prompt ----------------------------------------------------------------------------------

    def agent_for(self, *, alternative: bool) -> Agent:
        """The agent used to send: the conversation's, or the alternative one over it."""
        if alternative:
            return self._settings.alternative_agent.over(self._agent)
        return self._agent

    def send_prompt(self, *, alternative: bool) -> None:
        """Send the prompt with the conversation's agent, or with the alternative agent."""
        text = self._prompt.GetValue().strip()
        if not text or self._busy:
            return
        self._start_turn(text, self.agent_for(alternative=alternative))
        self._prompt.Clear()

    def _start_turn(self, text: str, _agent: Agent) -> None:
        # Placeholder until the runner exists: echo the prompt only.
        self._conversation.AppendText(_("You: {text}").format(text=text) + "\n")
        self.SetStatusText(_("Running Claude is not implemented yet."))

    def _on_prompt_key(self, event: wx.KeyEvent) -> None:
        if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            if event.ControlDown():
                self.send_prompt(alternative=False)
                return
            if event.ShiftDown():
                self.send_prompt(alternative=True)
                return
        event.Skip()  # a plain Enter adds a line break

    def _on_update_send(self, event: wx.UpdateUIEvent) -> None:
        event.Enable(not self._busy)

    def _on_update_interrupt(self, event: wx.UpdateUIEvent) -> None:
        event.Enable(self._busy)

    # Misc ------------------------------------------------------------------------------------

    def _show_error(self, message: str) -> None:
        wx.MessageBox(message, _("Error"), wx.OK | wx.ICON_ERROR, self)

    def _save_settings(self) -> None:
        try:
            self._settings.save()
        except SettingsError as error:
            self._show_error(_("Cannot save the settings.\n{error}").format(error=error))

    def _on_close(self, event: wx.CloseEvent) -> None:
        self._save_settings()
        event.Skip()
