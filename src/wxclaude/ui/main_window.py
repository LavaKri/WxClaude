"""Main window: conversation view, prompt field, send buttons and menus."""

from datetime import datetime
from pathlib import Path

import wx

from wxclaude.core.agents import Agent
from wxclaude.core.announcements import Announce
from wxclaude.core.claude_projects import (
    SessionInfo,
    choose_conversation,
    list_sessions,
)
from wxclaude.core.claude_settings import ToolSettings
from wxclaude.core.conversations import branch_name, default_name, new_conversation_id
from wxclaude.core.errors import (
    ClaudeSettingsError,
    JsonStoreError,
    SettingsError,
)
from wxclaude.core.runner import ClaudeRunner
from wxclaude.core.settings import Settings
from wxclaude.core.shortcuts import (
    SEND_ALTERNATIVE_COMMAND,
    SEND_COMMAND,
    ConfigurableCommand,
)
from wxclaude.core.usage import UsageTracker
from wxclaude.core.workspaces import describe
from wxclaude.i18n import _
from wxclaude.ui.agent_dialog import AgentDialog
from wxclaude.ui.conversation_name_dialog import ConversationNameDialog
from wxclaude.ui.conversation_view import ConversationView
from wxclaude.ui.feedback import Feedback
from wxclaude.ui.file_actions import FileActions
from wxclaude.ui.main_menu import MainMenu, MenuHandlers
from wxclaude.ui.message_actions import MessageActions
from wxclaude.ui.preferences_dialog import PreferencesDialog
from wxclaude.ui.run_controller import RunController, RunLinks
from wxclaude.ui.search_controller import SearchController
from wxclaude.ui.shortcut_keys import shortcut_from_event
from wxclaude.ui.workspace_opener import WorkspaceLinks, WorkspaceOpener
from wxclaude.ui.workspace_settings_dialog import WorkspaceSettingsDialog

_POSITION_WIDTH = 150
_STEP_WIDTH = 260


def _session_label(session: SessionInfo) -> str:
    """How a conversation is listed: its title (or the start of its id), then its last use."""
    when = datetime.fromtimestamp(session.last_used).strftime("%Y-%m-%d %H:%M")
    return _("{title} ({when})").format(title=session.title or session.id[:8], when=when)


class MainWindow(wx.Frame):
    """Top-level window: the conversation, the prompt, the menus, and what links them."""

    def __init__(self, settings: Settings, runner: ClaudeRunner | None = None) -> None:
        super().__init__(None, title=_("WxClaude"), size=wx.Size(900, 650))
        self._settings = settings
        self._agent = settings.default_agent
        self._closing = False
        self._usage = UsageTracker()  # gauges and spending, fed by the answers
        self._conversation_id = ""
        self._conversation_name = ""
        self._branch_count = 0  # branches made from the current conversation
        self._create_helpers()
        self._build_panel(runner or ClaudeRunner())
        self._build_menu_bar()
        # The position in the conversation, the step of Claude, then the messages.
        status_bar = self.CreateStatusBar(3)
        status_bar.SetStatusWidths([_POSITION_WIDTH, _STEP_WIDTH, -1])
        self._feedback.set_status(_("Ready"))
        self._feedback.apply_screen_reader_output(self._settings.screen_reader_output)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self._conversation.set_show_hidden(not settings.hide_system_messages)
        self._refresh_enabled()
        self._menu.refresh_recent()
        self._workspaces.restore_last_session()
        wx.CallAfter(self._focus_main_field)
        if settings.load_warning:
            wx.CallAfter(self._feedback.show_file_warning, settings.load_warning)

    def _create_helpers(self) -> None:
        """The objects that do the work for the window. The window's own methods are looked up at
        each call, so that they can be replaced."""
        self._feedback = Feedback(self, lambda: self._closing, self._settings.destination_for)
        self._files = FileActions(self, self._feedback)
        self._workspaces = WorkspaceOpener(
            self,
            self._feedback,
            self._settings,
            WorkspaceLinks(
                close_conversation=lambda: self._close_conversation(),
                select_conversation=lambda folder: self._select_workspace_conversation(folder),
                changed=lambda: self._workspace_changed(),
                save_settings=lambda: self._save_settings(),
            ),
        )
        self._actions = MessageActions(
            self,
            lambda dialog: self._feedback.modal(dialog),
            lambda message: self._feedback.show_error(message),
            lambda: self._conversation_id,
            self._usage,
            lambda message: self._conversation.exchange_of(message),
        )

    def _build_panel(self, runner: ClaudeRunner) -> None:
        """The conversation view, the prompt and the buttons, and the objects that need them."""
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
        self._run = RunController(
            self,
            runner,
            self._conversation,
            self._feedback,
            self._settings,
            self._usage,
            RunLinks(
                workspace=lambda: self._workspaces.workspace,
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

    def open_workspace(self, folder: Path) -> None:
        """Make ``folder`` the working folder; the conversation of another folder is closed."""
        self._workspaces.open(folder)

    def _workspace_changed(self) -> None:
        """A workspace was opened: the title and what is greyed follow."""
        self._update_title()
        self._refresh_enabled()

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
                open_workspace=lambda _event: self._workspaces.choose_folder(),
                open_project=lambda _event: self._workspaces.choose_project(),
                export=lambda _event: self._files.export(self._conversation.GetValue()),
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
                plans=lambda _event: self._actions.show_plans(),
                usage=lambda _event: self._actions.show_usage(),
                open_workspace_folder=lambda _event: self._files.open_folder(
                    self._workspaces.workspace
                ),
                workspace_settings=self._on_workspace_settings,
                preferences=self._on_preferences,
                show_help=lambda _event: self._files.show_help(self._settings.language),
                about=lambda _event: self._files.about(),
                recent_workspaces=lambda: self._workspaces.recent(),
                open_recent=lambda folder: self._workspaces.open_recent(folder),
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

    # Workspaces ------------------------------------------------------------------------------

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
        has_workspace = self._workspaces.workspace is not None
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
        if self._conversation_id and self._workspaces.state is not None:
            self._workspaces.state.remember(
                self._conversation_id, self._conversation_name, self._agent
            )
            self._save_state()

    def _start_new_conversation(self, name: str) -> None:
        self._set_conversation(new_conversation_id(), name)

    def _update_title(self) -> None:
        """Window title: the conversation, the workspace, then the application."""
        parts = [self._conversation_name] if self._conversation_name else []
        if self._workspaces.workspace is not None:
            parts.append(describe(str(self._workspaces.workspace))[0])
        parts.append(_("WxClaude"))
        self.SetTitle(" - ".join(parts))

    def _select_workspace_conversation(self, workspace: Path) -> None:
        """Select the remembered conversation of ``workspace``, else its most recent one.

        A workspace without any conversation stays without: none is created.
        """
        if self._workspaces.state is None:
            return
        sessions = list_sessions(workspace)
        self._workspaces.state.forget_missing({session.id for session in sessions})
        chosen = choose_conversation(sessions, self._workspaces.state.current_conversation)
        if chosen is not None:
            self._load_conversation(chosen)
            return
        # Nothing to talk to: the prompt and the buttons are greyed, the (empty) view says why.
        self._conversation.focus_last_prompt()
        self._feedback.say(Announce.NO_CONVERSATION)

    def _load_conversation(self, chosen: SessionInfo) -> bool:
        """Show the conversation ``chosen`` and make it current; False if it cannot be read."""
        session = self._feedback.read_session(chosen.path)
        if session is None:
            return False
        settings = self._settings
        record = (
            self._workspaces.state.conversations.get(chosen.id)
            if self._workspaces.state is not None
            else None
        )
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
        self._prompt.SetFocus()  # enabled by now: there is a conversation

    def _on_resume_conversation(self, _event: wx.CommandEvent) -> None:
        """Choose one of the conversations Claude Code holds for the workspace and show it."""
        if self._workspaces.workspace is None:
            return
        sessions = list_sessions(self._workspaces.workspace)
        if not sessions:
            self._feedback.show_error(_("This workspace has no conversation yet."))
            return
        labels = [_session_label(session) for session in sessions]
        index = self._feedback.choose(
            _("Resume a conversation"), _("Choose a conversation:"), labels
        )
        if index is not None:
            self._load_conversation(sessions[index])

    def _on_refresh_conversation(self, _event: wx.CommandEvent) -> None:
        """Read the session file again: messages added since (by the CLI) appear."""
        if self._workspaces.workspace is None or not self._conversation_id:
            return
        found = [
            s for s in list_sessions(self._workspaces.workspace) if s.id == self._conversation_id
        ]
        if not found:
            self._feedback.say(Announce.CONVERSATION_NOT_SAVED)
            return
        session = self._feedback.read_session(found[0].path)
        if session is None:
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

    def _on_new_branch(self, _event: wx.CommandEvent) -> None:
        # Until the Claude runner exists a branch keeps the text on screen under a new name.
        number = self._branch_count + 1
        proposal = branch_name(self._conversation_name, number)
        name = self._ask_conversation_name(_("New conversation branch"), proposal)
        if name is None:
            return
        self._branch_count = 0  # the new branch starts its own numbering
        self._start_new_conversation(name)  # a branch is a session of its own

    def _on_choose_agent(self, _event: wx.CommandEvent) -> None:
        with AgentDialog(self, self._agent) as dialog:
            if self._feedback.modal(dialog) == wx.ID_OK:
                self._agent = dialog.agent
                self._remember_conversation()

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
        if self._workspaces.workspace is None:
            return
        tool_settings = ToolSettings.load(self._workspaces.workspace)
        with WorkspaceSettingsDialog(
            self, tool_settings, local_only=self._settings.local_tools_only
        ) as dialog:
            if self._feedback.modal(dialog) != wx.ID_OK:
                return
        try:
            tool_settings.save()
        except ClaudeSettingsError as error:
            self._feedback.show_error(
                _("The settings could not be saved.\n{error}").format(error=error)
            )

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
        if self._workspaces.state is None:
            return
        try:
            self._workspaces.state.save()
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
