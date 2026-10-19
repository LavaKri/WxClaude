"""Main window: conversation view, prompt field, send buttons and menus."""

from datetime import datetime
from pathlib import Path

import wx

from wxclaude import __version__
from wxclaude.core.agents import Agent
from wxclaude.core.announcements import Announce, AnnouncementCenter, NullMessageSink
from wxclaude.core.claude_projects import SessionInfo, list_projects, list_sessions
from wxclaude.core.conversations import branch_name, default_name, new_conversation_id
from wxclaude.core.errors import (
    ExportError,
    ScreenReaderOutputError,
    SessionReadError,
    SettingsError,
)
from wxclaude.core.export import export_text
from wxclaude.core.messages import Message, Role
from wxclaude.core.session_reader import read_session
from wxclaude.core.settings import Settings
from wxclaude.core.shortcuts import (
    INTERRUPT_COMMAND,
    NEW_CONVERSATION_COMMAND,
    OPEN_WORKSPACE_COMMAND,
    RESUME_CONVERSATION_COMMAND,
    SEND_ALTERNATIVE_COMMAND,
    SEND_COMMAND,
    TASKS_COMMAND,
    ConfigurableCommand,
)
from wxclaude.core.workspaces import add_recent, describe, remove_missing, workspace_label
from wxclaude.i18n import _
from wxclaude.ui.agent_dialog import AgentDialog
from wxclaude.ui.conversation_name_dialog import ConversationNameDialog
from wxclaude.ui.conversation_view import ConversationView
from wxclaude.ui.message_sinks import create_sink
from wxclaude.ui.options_dialog import OptionsDialog
from wxclaude.ui.shortcut_keys import shortcut_from_event
from wxclaude.ui.tasks_dialog import TasksDialog


def _session_label(session: SessionInfo) -> str:
    """How a conversation is listed: its title (or the start of its id), then its last use."""
    when = datetime.fromtimestamp(session.last_used).strftime("%Y-%m-%d %H:%M")
    return _("{title} ({when})").format(title=session.title or session.id[:8], when=when)


class MainWindow(wx.Frame):
    """Top-level window. Skeleton: Claude is not launched yet, sending only echoes the prompt."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(None, title=_("WxClaude"), size=wx.Size(900, 650))
        self._settings = settings
        self._workspace: Path | None = None
        self._agent = settings.default_agent
        self._busy = False  # True while Claude is answering (set by the runner, later)
        self._recent_ids: dict[int, str] = {}
        self._command_items: list[tuple[ConfigurableCommand, wx.MenuItem, str]] = []
        self._output_id: str | None = None  # the screen reader output in use
        self._conversation_id = ""
        self._conversation_name = ""
        self._branch_count = 0  # branches made from the current conversation

        panel = wx.Panel(self)
        conversation_label = wx.StaticText(panel, label=_("Con&versation"))
        self._conversation = ConversationView(panel, self._say)
        prompt_label = wx.StaticText(panel, label=_("&Prompt"))
        self._prompt = wx.TextCtrl(panel, style=wx.TE_MULTILINE, name=_("Prompt"))
        self._prompt.Bind(wx.EVT_KEY_DOWN, self._on_prompt_key)

        self._send_button = wx.Button(panel)  # the labels come from the shortcuts, see
        self._alternative_button = wx.Button(panel)  # _apply_shortcuts
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
        self._announcements = AnnouncementCenter(on_error=self._on_screen_reader_error)
        self._apply_screen_reader_output()
        self.Bind(wx.EVT_MENU_OPEN, self._on_menu_open)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self._refresh_enabled()
        self._refresh_recent_menu()
        self._restore_last_session()
        wx.CallAfter(self._focus_main_field)

    @property
    def conversation_id(self) -> str:
        """Identifier of the current conversation (the session of the Claude Code CLI)."""
        return self._conversation_id

    # Menus -----------------------------------------------------------------------------------

    def _build_menu_bar(self) -> None:
        self._file_menu = wx.Menu()
        open_item = self._file_menu.Append(wx.ID_ANY, _("&Open workspace…"))
        self._command_items.append((OPEN_WORKSPACE_COMMAND, open_item, _("&Open workspace…")))
        projects_item = self._file_menu.Append(wx.ID_ANY, _("Open from Claude &projects…"))
        export_item = self._file_menu.Append(wx.ID_ANY, _("&Export the conversation…"))
        self._file_menu.AppendSeparator()
        self._recent_menu = wx.Menu()
        self._recent_item = self._file_menu.AppendSubMenu(self._recent_menu, _("&Recent"))
        quit_item = self._file_menu.Append(wx.ID_EXIT, _("&Quit\tCtrl+Q"))

        conversation_menu = wx.Menu()
        new_item = conversation_menu.Append(wx.ID_ANY, _("&New conversation"))
        resume_item = conversation_menu.Append(wx.ID_ANY, _("&Resume a conversation…"))
        rename_item = conversation_menu.Append(wx.ID_ANY, _("Ren&ame the conversation"))
        branch_item = conversation_menu.Append(wx.ID_ANY, _("New conversation &branch"))
        delete_item = conversation_menu.Append(wx.ID_ANY, _("&Delete the conversation"))
        self._interrupt_item = conversation_menu.Append(wx.ID_ANY, _("&Interrupt Claude"))
        self._command_items += [
            (NEW_CONVERSATION_COMMAND, new_item, _("&New conversation")),
            (RESUME_CONVERSATION_COMMAND, resume_item, _("&Resume a conversation…")),
            (INTERRUPT_COMMAND, self._interrupt_item, _("&Interrupt Claude")),
        ]
        agent_item = conversation_menu.Append(wx.ID_ANY, _("&Modify the agent…"))
        delete_item.Enable(False)  # needs the delete feature (a later milestone)

        tools_menu = wx.Menu()
        tasks_item = tools_menu.Append(wx.ID_ANY, _("Task &list…"))
        self._command_items.append((TASKS_COMMAND, tasks_item, _("Task &list…")))
        options_item = tools_menu.Append(wx.ID_ANY, _("&Options…"))

        # A conversation belongs to a workspace: without a workspace only the items that open
        # one are available, and without a conversation those that need one are greyed.
        self._needs_workspace = [new_item, resume_item]
        self._needs_conversation = [export_item, rename_item, branch_item, agent_item, tasks_item]

        help_menu = wx.Menu()
        about_item = help_menu.Append(wx.ID_ABOUT, _("&About"))

        menu_bar = wx.MenuBar()
        menu_bar.Append(self._file_menu, _("&File"))
        menu_bar.Append(conversation_menu, _("&Conversation"))
        menu_bar.Append(tools_menu, _("&Tools"))
        menu_bar.Append(help_menu, _("&Help"))
        self.SetMenuBar(menu_bar)
        self._apply_shortcuts()

        self.Bind(wx.EVT_MENU, self._on_open_workspace, open_item)
        self.Bind(wx.EVT_MENU, self._on_open_project, projects_item)
        self.Bind(wx.EVT_MENU, self._on_tasks, tasks_item)
        self.Bind(wx.EVT_MENU, self._on_export, export_item)
        self.Bind(wx.EVT_MENU, lambda _event: self.Close(), quit_item)
        self.Bind(wx.EVT_MENU, self._on_new_conversation, new_item)
        self.Bind(wx.EVT_MENU, self._on_resume_conversation, resume_item)
        self.Bind(wx.EVT_MENU, self._on_rename_conversation, rename_item)
        self.Bind(wx.EVT_MENU, self._on_new_branch, branch_item)
        self.Bind(wx.EVT_MENU, self._on_choose_agent, agent_item)
        self.Bind(wx.EVT_MENU, self._on_options, options_item)
        self.Bind(wx.EVT_MENU, self._on_about, about_item)
        self.Bind(wx.EVT_UPDATE_UI, self._on_update_interrupt, self._interrupt_item)

    def _apply_shortcuts(self) -> None:
        """Show (and activate) the shortcut of each configurable command in its menu item."""
        for command, item, text in self._command_items:
            shortcut = self._settings.shortcut_for(command)
            item.SetItemLabel(f"{text}\t{shortcut}" if shortcut else text)
        self._send_button.SetLabel(self._send_label(SEND_COMMAND))
        self._alternative_button.SetLabel(self._send_label(SEND_ALTERNATIVE_COMMAND))

    def _send_label(self, command: ConfigurableCommand) -> str:
        """Label of a send button: its action, then its shortcut (the screen reader says it)."""
        shortcut = self._settings.shortcut_for(command)
        if command is SEND_COMMAND:
            return _("&Send ({shortcut})").format(shortcut=shortcut) if shortcut else _("&Send")
        if shortcut:
            return _("Send with the &alternative agent ({shortcut})").format(shortcut=shortcut)
        return _("Send with the &alternative agent")

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
            item = self._recent_menu.Append(wx.ID_ANY, workspace_label(folder).replace("&", "&&"))
            self._recent_ids[item.GetId()] = folder
            self.Bind(wx.EVT_MENU, self._on_recent, item)
        self._recent_item.Enable(bool(self._recent_ids))

    # Workspaces ------------------------------------------------------------------------------

    def open_workspace(self, folder: Path) -> None:
        """Make ``folder`` the working folder; the conversation of another folder is closed."""
        if folder != self._workspace:
            self._close_conversation()
        self._set_workspace(folder)

    def _set_workspace(self, folder: Path) -> None:
        """Make ``folder`` the working folder and remember it in the recent list."""
        self._workspace = folder
        self._settings.last_workspace = str(folder)
        self._settings.recent_workspaces = add_recent(self._settings.recent_workspaces, folder)
        self._update_title()
        self._refresh_enabled()
        self._say(Announce.WORKSPACE_OPENED, folder=folder)
        self._save_settings()

    def _on_open_project(self, _event: wx.CommandEvent) -> None:
        """Open one of the folders Claude Code has already worked in."""
        projects = list_projects()
        if not projects:
            self._show_error(_("Claude Code has no project yet."))
            return
        labels = [workspace_label(str(project.folder)) for project in projects]
        with wx.SingleChoiceDialog(
            self, _("Choose a project:"), _("Open from Claude projects"), labels
        ) as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                self.open_workspace(projects[dialog.GetSelection()].folder)

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

    def _ask_conversation_name(self, title: str, proposal: str) -> str | None:
        """Ask for a conversation name, the proposal being selected; None if cancelled."""
        with ConversationNameDialog(self, title, proposal) as dialog:
            return dialog.name if dialog.ShowModal() == wx.ID_OK else None

    def _set_conversation(self, conversation_id: str, name: str) -> None:
        """Make the conversation ``conversation_id`` the current one and remember it."""
        self._conversation_id = conversation_id
        self._settings.last_conversation_id = conversation_id
        self._set_conversation_name(name)
        self._refresh_enabled()

    def _close_conversation(self) -> None:
        """No conversation is current any more (a conversation belongs to its workspace)."""
        self._conversation.clear_messages()
        self._prompt.Clear()
        self._conversation_id = ""
        self._conversation_name = ""
        self._branch_count = 0
        self._settings.last_conversation_id = ""
        self._settings.last_conversation_name = ""
        self._update_title()
        self._refresh_enabled()

    def _refresh_enabled(self) -> None:
        """Grey out what needs a workspace or a conversation that is not there."""
        has_workspace = self._workspace is not None
        has_conversation = bool(self._conversation_id)
        for item in self._needs_workspace:
            item.Enable(has_workspace)
        for item in self._needs_conversation:
            item.Enable(has_conversation)
        self._prompt.Enable(has_conversation)
        self._interrupt_item.Enable(self._busy)

    @property
    def can_send(self) -> bool:
        """Can a prompt be sent now? It needs a conversation, and Claude must not be answering."""
        return bool(self._conversation_id) and not self._busy

    def _set_conversation_name(self, name: str) -> None:
        self._conversation_name = name
        self._settings.last_conversation_name = name
        self._update_title()

    def _start_new_conversation(self, name: str) -> None:
        self._set_conversation(new_conversation_id(), name)

    def _update_title(self) -> None:
        """Window title: the conversation, the workspace, then the application."""
        parts = [self._conversation_name] if self._conversation_name else []
        if self._workspace is not None:
            parts.append(describe(str(self._workspace))[0])
        parts.append(_("WxClaude"))
        self.SetTitle(" - ".join(parts))

    def _restore_last_session(self) -> None:
        """At startup: open the last workspace and select the conversation that was current.

        Only the identifier and the name of the conversation are restored, nothing is loaded.
        Without the option, at the first start, or if that workspace no longer exists, there is
        no workspace and no conversation: only what opens a workspace is available.
        """
        settings = self._settings
        if not (settings.reopen_last and settings.last_workspace):
            return
        folder = Path(settings.last_workspace)
        if not folder.is_dir():
            return
        self._set_workspace(folder)
        if settings.last_conversation_id and settings.last_conversation_name:
            self._set_conversation(settings.last_conversation_id, settings.last_conversation_name)

    def _on_new_conversation(self, _event: wx.CommandEvent) -> None:
        number = self._settings.conversation_counter
        name = self._ask_conversation_name(_("New conversation"), default_name(number))
        if name is None:
            return
        self._settings.conversation_counter = number + 1
        self._conversation.clear_messages()
        self._prompt.Clear()
        self._agent = self._settings.default_agent
        self._branch_count = 0
        self._start_new_conversation(name)
        self._say(Announce.NEW_CONVERSATION, name=name)
        self._prompt.SetFocus()  # enabled by now: there is a conversation

    def _on_resume_conversation(self, _event: wx.CommandEvent) -> None:
        """Choose one of the conversations Claude Code holds for the workspace and show it."""
        if self._workspace is None:
            return
        sessions = list_sessions(self._workspace)
        if not sessions:
            self._show_error(_("This workspace has no conversation yet."))
            return
        labels = [_session_label(session) for session in sessions]
        with wx.SingleChoiceDialog(
            self, _("Choose a conversation:"), _("Resume a conversation"), labels
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            chosen = sessions[dialog.GetSelection()]
        try:
            session = read_session(chosen.path)
        except SessionReadError as error:
            self._show_error(_("Cannot read the conversation.\n{error}").format(error=error))
            return
        name = chosen.title
        if not name:
            number = self._settings.conversation_counter
            name = default_name(number)
            self._settings.conversation_counter = number + 1
        self._conversation.set_messages(session.messages)
        self._prompt.Clear()
        self._agent = Agent.from_dict(
            {"model": session.last_model, "permission_mode": session.last_permission_mode}
        ).over(self._settings.default_agent)
        self._branch_count = 0
        self._set_conversation(chosen.id, name)
        self._say(Announce.CONVERSATION_RESUMED, name=name)
        self._conversation.SetFocus()

    def _on_rename_conversation(self, _event: wx.CommandEvent) -> None:
        name = self._ask_conversation_name(_("Rename the conversation"), self._conversation_name)
        if name is not None:
            self._set_conversation_name(name)
            self._say(Announce.CONVERSATION_RENAMED, name=name)

    def _on_new_branch(self, _event: wx.CommandEvent) -> None:
        # Until the Claude runner exists a branch keeps the text on screen under a new name.
        number = self._branch_count + 1
        proposal = branch_name(self._conversation_name, number)
        name = self._ask_conversation_name(_("New conversation branch"), proposal)
        if name is None:
            return
        self._branch_count = 0  # the new branch starts its own numbering
        self._start_new_conversation(name)  # a branch is a session of its own
        self._say(Announce.CONVERSATION_BRANCHED, name=name)

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
        self._say(Announce.CONVERSATION_EXPORTED, path=path)

    def _on_choose_agent(self, _event: wx.CommandEvent) -> None:
        with AgentDialog(self, self._agent) as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                self._agent = dialog.agent
                self._say(Announce.AGENT_UPDATED)

    def _on_options(self, _event: wx.CommandEvent) -> None:
        with OptionsDialog(self, self._settings) as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                dialog.apply(self._settings)
                self._apply_shortcuts()
                self._apply_screen_reader_output()
                self._save_settings()

    def _focus_main_field(self) -> None:
        """The prompt when there is a conversation, else the conversation view."""
        (self._prompt if self._conversation_id else self._conversation).SetFocus()

    def _on_tasks(self, _event: wx.CommandEvent) -> None:
        with TasksDialog(self) as dialog:
            dialog.ShowModal()

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
        if not text or not self.can_send:
            return
        self._start_turn(text, self.agent_for(alternative=alternative))
        self._prompt.Clear()

    def _start_turn(self, text: str, _agent: Agent) -> None:
        # Placeholder until the runner exists: echo the prompt only.
        number = len(self._conversation.document.spans)
        self._conversation.append_message(Message(f"local-{number}", Role.USER, text))
        self.SetStatusText(_("Running Claude is not implemented yet."))

    def _on_prompt_key(self, event: wx.KeyEvent) -> None:
        shortcut = shortcut_from_event(event)
        if shortcut:
            if shortcut == self._settings.shortcut_for(SEND_COMMAND):
                self.send_prompt(alternative=False)
                return
            if shortcut == self._settings.shortcut_for(SEND_ALTERNATIVE_COMMAND):
                self.send_prompt(alternative=True)
                return
        event.Skip()  # a plain Enter adds a line break

    def _on_update_send(self, event: wx.UpdateUIEvent) -> None:
        event.Enable(self.can_send)

    def _on_update_interrupt(self, event: wx.UpdateUIEvent) -> None:
        event.Enable(self._busy)

    # Misc ------------------------------------------------------------------------------------

    def _say(self, announce: Announce, **values: object) -> None:
        """Show an announcement in the status bar and send it to the screen reader output."""
        self.SetStatusText(self._announcements.notify(announce, **values))

    def _apply_screen_reader_output(self) -> None:
        """Connect the announcements to the output chosen in the options."""
        if self._settings.screen_reader_output == self._output_id:
            return
        self._output_id = self._settings.screen_reader_output
        try:
            sink = create_sink(self._settings.screen_reader_output, self)
        except ScreenReaderOutputError as error:
            sink = NullMessageSink()
            self._on_screen_reader_error(error)
        self._announcements.message_sink.close()
        self._announcements.message_sink = sink

    def _on_screen_reader_error(self, error: ScreenReaderOutputError) -> None:
        self._show_error(_("The screen reader output cannot be used.\n{error}").format(error=error))

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
