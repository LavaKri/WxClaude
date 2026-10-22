"""Main window: conversation view, prompt field, send buttons and menus."""

from datetime import datetime
from pathlib import Path

import wx

from wxclaude import __version__
from wxclaude.core.agents import Agent
from wxclaude.core.announcements import Announce
from wxclaude.core.claude_projects import (
    SessionInfo,
    choose_conversation,
    list_projects,
    list_sessions,
)
from wxclaude.core.claude_settings import ToolSettings
from wxclaude.core.conversations import branch_name, default_name, new_conversation_id
from wxclaude.core.errors import (
    ClaudeSettingsError,
    ExportError,
    JsonStoreError,
    SessionReadError,
    SettingsError,
)
from wxclaude.core.export import export_text
from wxclaude.core.runner import ClaudeRunner
from wxclaude.core.session_reader import read_session
from wxclaude.core.settings import Settings
from wxclaude.core.shortcuts import (
    SEND_ALTERNATIVE_COMMAND,
    SEND_COMMAND,
    ConfigurableCommand,
)
from wxclaude.core.usage import UsageTracker
from wxclaude.core.workspace_state import WorkspaceState
from wxclaude.core.workspaces import add_recent, describe, remove_missing, workspace_label
from wxclaude.i18n import _
from wxclaude.ui import desktop
from wxclaude.ui.agent_dialog import AgentDialog
from wxclaude.ui.conversation_name_dialog import ConversationNameDialog
from wxclaude.ui.conversation_view import ConversationView
from wxclaude.ui.feedback import Feedback
from wxclaude.ui.main_menu import MainMenu, MenuHandlers
from wxclaude.ui.message_actions import MessageActions
from wxclaude.ui.preferences_dialog import PreferencesDialog
from wxclaude.ui.run_controller import RunController, RunLinks
from wxclaude.ui.search_controller import SearchController
from wxclaude.ui.shortcut_keys import shortcut_from_event
from wxclaude.ui.workspace_settings_dialog import WorkspaceSettingsDialog

_POSITION_WIDTH = 150


def _session_label(session: SessionInfo) -> str:
    """How a conversation is listed: its title (or the start of its id), then its last use."""
    when = datetime.fromtimestamp(session.last_used).strftime("%Y-%m-%d %H:%M")
    return _("{title} ({when})").format(title=session.title or session.id[:8], when=when)


class MainWindow(wx.Frame):
    """Top-level window: the conversation, the prompt, the menus, and what links them."""

    def __init__(self, settings: Settings, runner: ClaudeRunner | None = None) -> None:
        super().__init__(None, title=_("WxClaude"), size=wx.Size(900, 650))
        self._settings = settings
        self._workspace: Path | None = None
        self._state: WorkspaceState | None = None  # what is remembered about the workspace
        self._agent = settings.default_agent
        self._closing = False
        self._feedback = Feedback(self, lambda: self._closing)
        self._usage = UsageTracker()  # gauges and spending, fed by the answers
        self._conversation_id = ""
        self._conversation_name = ""
        self._branch_count = 0  # branches made from the current conversation

        # The window's own methods are looked up at each call, so that they can be replaced.
        self._actions = MessageActions(
            self,
            lambda dialog: self._feedback.modal(dialog),
            lambda announce, **values: self._feedback.say(announce, **values),
            lambda message: self._feedback.show_error(message),
            lambda: self._conversation_id,
            self._usage,
        )
        panel = wx.Panel(self)
        conversation_label = wx.StaticText(panel, label=_("Con&versation"))
        self._conversation = ConversationView(
            panel,
            self._feedback.say,
            lambda action, message, line: self._actions.act(action, message, line),
            self._feedback.show_position,
        )
        self._search = SearchController(
            self._conversation,
            lambda dialog: self._feedback.modal(dialog),
            lambda announce, **values: self._feedback.say(announce, **values),
            lambda message: self._feedback.show_info(message),
        )
        # The window is looked up at each call, so that its methods can be replaced.
        self._run = RunController(
            self,
            runner or ClaudeRunner(),
            self._conversation,
            self._feedback,
            settings,
            self._usage,
            RunLinks(
                workspace=lambda: self._workspace,
                conversation_id=lambda: self._conversation_id,
                is_closing=lambda: self._closing,
                state_changed=lambda: self._refresh_enabled(),
            ),
        )
        self._apply_claude_path()
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
        self._interrupt_button.Bind(wx.EVT_BUTTON, self._on_interrupt)

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
        status_bar = self.CreateStatusBar(2)  # the position in the conversation, then the messages
        status_bar.SetStatusWidths([_POSITION_WIDTH, -1])
        self._feedback.set_status(_("Ready"))
        self._feedback.apply_screen_reader_output(self._settings.screen_reader_output)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self._conversation.set_show_hidden(not settings.hide_system_messages)
        self._refresh_enabled()
        self._menu.refresh_recent()
        self._restore_last_session()
        wx.CallAfter(self._focus_main_field)
        if settings.load_warning:
            wx.CallAfter(self._feedback.show_file_warning, settings.load_warning)

    @property
    def conversation_id(self) -> str:
        """Identifier of the current conversation (the session of the Claude Code CLI)."""
        return self._conversation_id

    # Menus -----------------------------------------------------------------------------------

    def _build_menu_bar(self) -> None:
        """The menu bar (``ui/main_menu.py``), told what each item does."""
        search = self._search
        self._menu = MainMenu(
            self,
            MenuHandlers(
                open_workspace=self._on_open_workspace,
                open_project=self._on_open_project,
                export=self._on_export,
                quit=lambda _event: self.Close(),
                new_conversation=self._on_new_conversation,
                resume_conversation=self._on_resume_conversation,
                refresh_conversation=self._on_refresh_conversation,
                rename_conversation=self._on_rename_conversation,
                new_branch=self._on_new_branch,
                interrupt=self._on_interrupt,
                update_interrupt=self._on_update_interrupt,
                choose_agent=self._on_choose_agent,
                find=lambda _event: search.find(),
                find_next=lambda _event: search.find_next(),
                find_previous=lambda _event: search.find_previous(),
                tasks=lambda _event: self._actions.show_tasks(),
                usage=lambda _event: self._actions.show_usage(),
                open_workspace_folder=self._on_open_workspace_folder,
                workspace_settings=self._on_workspace_settings,
                preferences=self._on_preferences,
                about=self._on_about,
                recent_workspaces=self._recent_workspaces,
                open_recent=self._open_recent,
            ),
        )
        self._apply_shortcuts()

    def _apply_shortcuts(self) -> None:
        """Show (and activate) the shortcuts in the menus and in the labels of the send buttons."""
        self._menu.apply_shortcuts(self._settings.shortcut_for)
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

    def _recent_workspaces(self) -> list[str]:
        """The recent workspaces whose folder still exists (the others are dropped)."""
        self._settings.recent_workspaces = remove_missing(self._settings.recent_workspaces)
        return list(self._settings.recent_workspaces)

    # Workspaces ------------------------------------------------------------------------------

    def open_workspace(self, folder: Path) -> None:
        """Make ``folder`` the working folder; the conversation of another folder is closed."""
        changed = folder != self._workspace
        if changed:
            self._close_conversation()
        self._set_workspace(folder)
        if changed:
            self._select_workspace_conversation(folder)

    def _set_workspace(self, folder: Path) -> None:
        """Make ``folder`` the working folder and remember it in the recent list."""
        if self._state is None or folder != self._workspace:
            self._state = WorkspaceState.load(folder, self._settings.workspaces_dir)
            if self._state.warning:
                self._feedback.show_file_warning(self._state.warning)
        self._workspace = folder
        self._settings.last_workspace = str(folder)
        self._settings.recent_workspaces = add_recent(self._settings.recent_workspaces, folder)
        self._update_title()
        self._refresh_enabled()
        self._feedback.say(Announce.WORKSPACE_OPENED, folder=folder)
        self._save_settings()

    def _on_open_project(self, _event: wx.CommandEvent) -> None:
        """Open one of the folders Claude Code has already worked in."""
        projects = list_projects()
        if not projects:
            self._feedback.show_error(_("Claude Code has no project yet."))
            return
        labels = [workspace_label(str(project.folder)) for project in projects]
        with wx.SingleChoiceDialog(
            self, _("Choose a project:"), _("Open from Claude projects"), labels
        ) as dialog:
            if self._feedback.modal(dialog) == wx.ID_OK:
                self.open_workspace(projects[dialog.GetSelection()].folder)

    def _on_open_workspace(self, _event: wx.CommandEvent) -> None:
        default = str(self._workspace) if self._workspace else ""
        with wx.DirDialog(
            self,
            _("Choose the working folder"),
            defaultPath=default,
            style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST,
        ) as dialog:
            if self._feedback.modal(dialog) == wx.ID_OK:
                self.open_workspace(Path(dialog.GetPath()))

    def _open_recent(self, folder: str) -> None:
        """Open a recent workspace; a folder that is gone is dropped from the list."""
        if Path(folder).is_dir():
            self.open_workspace(Path(folder))
            return
        self._settings.recent_workspaces = remove_missing(self._settings.recent_workspaces)
        self._feedback.show_error(
            _("The folder {folder} no longer exists. It was removed from the recent list.").format(
                folder=folder
            )
        )

    # Conversation ----------------------------------------------------------------------------

    def _ask_conversation_name(self, title: str, proposal: str) -> str | None:
        """Ask for a conversation name, the proposal being selected; None if cancelled."""
        with ConversationNameDialog(self, title, proposal) as dialog:
            return dialog.name if self._feedback.modal(dialog) == wx.ID_OK else None

    def _set_conversation(self, conversation_id: str, name: str) -> None:
        """Make the conversation ``conversation_id`` the current one and remember it."""
        if conversation_id != self._conversation_id:
            self._usage.start_conversation()
        self._conversation_id = conversation_id
        self._set_conversation_name(name)  # also remembers the conversation
        self._refresh_enabled()

    def _close_conversation(self) -> None:
        """No conversation is current any more (a conversation belongs to its workspace)."""
        self._conversation.clear_messages()
        self._prompt.Clear()
        self._conversation_id = ""
        self._conversation_name = ""
        self._branch_count = 0
        self._usage.start_conversation()
        self._update_title()
        self._refresh_enabled()

    def _refresh_enabled(self) -> None:
        """Grey out what needs a workspace or a conversation that is not there."""
        has_workspace = self._workspace is not None
        has_conversation = bool(self._conversation_id)
        self._menu.refresh_enabled(
            has_workspace=has_workspace, has_conversation=has_conversation, busy=self._run.busy
        )
        self._prompt.Enable(has_conversation)

    @property
    def can_send(self) -> bool:
        """Can a prompt be sent now? It needs a conversation, and Claude must not be answering."""
        return bool(self._conversation_id) and not self._run.busy

    def _set_conversation_name(self, name: str) -> None:
        self._conversation_name = name
        self._remember_conversation()
        self._update_title()

    def _remember_conversation(self) -> None:
        """Keep what the settings remember: the current conversation of the workspace, its name
        and its main agent."""
        if self._conversation_id and self._state is not None:
            self._state.remember(self._conversation_id, self._conversation_name, self._agent)
            self._save_state()

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
        """At startup: open the last workspace and select its conversation.

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
        self._select_workspace_conversation(folder)

    def _select_workspace_conversation(self, workspace: Path) -> None:
        """Select the remembered conversation of ``workspace``, else its most recent one.

        A workspace without any conversation stays without: none is created.
        """
        if self._state is None:
            return
        sessions = list_sessions(workspace)
        self._state.forget_missing({session.id for session in sessions})
        chosen = choose_conversation(sessions, self._state.current_conversation)
        if chosen is not None:
            self._load_conversation(chosen)
            return
        # Nothing to talk to: the prompt and the buttons are greyed, the (empty) view says why.
        self._conversation.focus_last_prompt()
        self._feedback.say(Announce.NO_CONVERSATION)

    def _load_conversation(self, chosen: SessionInfo) -> bool:
        """Show the conversation ``chosen`` and make it current; False if it cannot be read."""
        try:
            session = read_session(chosen.path)
        except SessionReadError as error:
            self._feedback.show_error(
                _("Cannot read the conversation.\n{error}").format(error=error)
            )
            return False
        settings = self._settings
        record = self._state.conversations.get(chosen.id) if self._state is not None else None
        name = (record.name if record else "") or chosen.title
        if not name:
            name = default_name(settings.conversation_counter)
            settings.conversation_counter += 1
        # A conversation WxClaude knows nothing about takes the agent of its last message as its
        # main agent (it is remembered by _set_conversation below).
        self._agent = (
            record.agent.over(settings.default_agent)
            if record
            else session.last_agent.over(settings.default_agent)
        )
        self._conversation.set_messages(session.messages)
        self._prompt.Clear()
        self._branch_count = 0
        self._set_conversation(chosen.id, name)
        self._conversation.focus_last_prompt()
        self._feedback.say(Announce.CONVERSATION_RESUMED, name=name)
        return True

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
        self._feedback.say(Announce.NEW_CONVERSATION, name=name)
        self._prompt.SetFocus()  # enabled by now: there is a conversation

    def _on_resume_conversation(self, _event: wx.CommandEvent) -> None:
        """Choose one of the conversations Claude Code holds for the workspace and show it."""
        if self._workspace is None:
            return
        sessions = list_sessions(self._workspace)
        if not sessions:
            self._feedback.show_error(_("This workspace has no conversation yet."))
            return
        labels = [_session_label(session) for session in sessions]
        with wx.SingleChoiceDialog(
            self, _("Choose a conversation:"), _("Resume a conversation"), labels
        ) as dialog:
            if self._feedback.modal(dialog) != wx.ID_OK:
                return
            chosen = sessions[dialog.GetSelection()]
        self._load_conversation(chosen)

    def _on_refresh_conversation(self, _event: wx.CommandEvent) -> None:
        """Read the session file again: messages added since (by the CLI) appear."""
        if self._workspace is None or not self._conversation_id:
            return
        found = [s for s in list_sessions(self._workspace) if s.id == self._conversation_id]
        if not found:
            self._feedback.say(Announce.CONVERSATION_NOT_SAVED)
            return
        try:
            session = read_session(found[0].path)
        except SessionReadError as error:
            self._feedback.show_error(
                _("Cannot read the conversation.\n{error}").format(error=error)
            )
            return
        view = self._conversation
        before = len(view.document.spans)
        view.set_messages(session.messages)
        view.focus_last_prompt()
        self._feedback.say(
            Announce.CONVERSATION_REFRESHED, count=max(0, len(view.document.spans) - before)
        )

    def _on_rename_conversation(self, _event: wx.CommandEvent) -> None:
        name = self._ask_conversation_name(_("Rename the conversation"), self._conversation_name)
        if name is not None:
            self._set_conversation_name(name)
            self._feedback.say(Announce.CONVERSATION_RENAMED, name=name)

    def _on_new_branch(self, _event: wx.CommandEvent) -> None:
        # Until the Claude runner exists a branch keeps the text on screen under a new name.
        number = self._branch_count + 1
        proposal = branch_name(self._conversation_name, number)
        name = self._ask_conversation_name(_("New conversation branch"), proposal)
        if name is None:
            return
        self._branch_count = 0  # the new branch starts its own numbering
        self._start_new_conversation(name)  # a branch is a session of its own
        self._feedback.say(Announce.CONVERSATION_BRANCHED, name=name)

    def _on_export(self, _event: wx.CommandEvent) -> None:
        with wx.FileDialog(
            self,
            _("Export the conversation"),
            defaultFile=_("conversation.txt"),
            wildcard=_("Text files (*.txt)|*.txt|Markdown files (*.md)|*.md"),
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dialog:
            if self._feedback.modal(dialog) != wx.ID_OK:
                return
            path = Path(dialog.GetPath())
        try:
            export_text(path, self._conversation.GetValue())
        except ExportError as error:
            self._feedback.show_error(
                _("Cannot export the conversation.\n{error}").format(error=error)
            )
            return
        self._feedback.say(Announce.CONVERSATION_EXPORTED, path=path)

    def _on_choose_agent(self, _event: wx.CommandEvent) -> None:
        with AgentDialog(self, self._agent) as dialog:
            if self._feedback.modal(dialog) == wx.ID_OK:
                self._agent = dialog.agent
                self._remember_conversation()
                self._feedback.say(Announce.AGENT_UPDATED)

    def _on_preferences(self, _event: wx.CommandEvent) -> None:
        with PreferencesDialog(self, self._settings) as dialog:
            if self._feedback.modal(dialog) == wx.ID_OK:
                dialog.apply(self._settings)
                self._conversation.set_show_hidden(not self._settings.hide_system_messages)
                self._apply_shortcuts()
                self._feedback.apply_screen_reader_output(self._settings.screen_reader_output)
                self._apply_claude_path()
                self._save_settings()

    def _focus_main_field(self) -> None:
        """At startup the focus is on the conversation view, at the last prompt if there is one."""
        self._conversation.focus_last_prompt()

    def _on_open_workspace_folder(self, _event: wx.CommandEvent) -> None:
        """Show the folder of the workspace in the file explorer."""
        folder = self._workspace
        if folder is None:
            return
        if not folder.is_dir():
            self._feedback.show_error(
                _("The folder {folder} no longer exists.").format(folder=folder)
            )
        elif not desktop.launch_folder(folder):
            self._feedback.show_error(
                _("The folder {folder} cannot be opened in the file explorer.").format(
                    folder=folder
                )
            )

    def _on_about(self, _event: wx.CommandEvent) -> None:
        message = _("WxClaude {version}").format(version=__version__)
        self._feedback.message_box(message, _("About"), wx.ICON_INFORMATION)

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
        if self._run.start(text, self.agent_for(alternative=alternative)):
            self._prompt.Clear()
            self._conversation.focus_last_prompt()  # the prompt that was just sent

    def _on_workspace_settings(self, _event: wx.CommandEvent) -> None:
        """The permission rules of the workspace, in the settings files of Claude Code."""
        if self._workspace is None:
            return
        tool_settings = ToolSettings.load(self._workspace)
        with WorkspaceSettingsDialog(
            self, tool_settings, local_only=self._settings.local_tools_only
        ) as dialog:
            if self._feedback.modal(dialog) != wx.ID_OK:
                return
        try:
            written = tool_settings.save()
        except ClaudeSettingsError as error:
            self._feedback.show_error(
                _("The settings could not be saved.\n{error}").format(error=error)
            )
            return
        if written:
            self._feedback.say(Announce.WORKSPACE_SETTINGS_SAVED)

    def _on_interrupt(self, _event: wx.CommandEvent) -> None:
        self._run.interrupt()

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
        event.Enable(self._run.busy)

    # Misc ------------------------------------------------------------------------------------

    def _apply_claude_path(self) -> None:
        """Tell the runner which claude executable to start: the chosen file, or the PATH."""
        settings = self._settings
        self._run.runner.claude_path = "" if settings.claude_auto_search else settings.claude_path

    def _save_state(self) -> None:
        if self._state is None:
            return
        try:
            self._state.save()
        except JsonStoreError as error:
            self._feedback.show_error(
                _("Cannot save the workspace data.\n{error}").format(error=error)
            )

    def _save_settings(self) -> None:
        try:
            self._settings.save()
        except SettingsError as error:
            self._feedback.show_error(_("Cannot save the settings.\n{error}").format(error=error))

    def _on_close(self, event: wx.CloseEvent) -> None:
        self._closing = True
        self._run.runner.interrupt()
        self._save_settings()
        event.Skip()
