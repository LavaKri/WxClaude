"""Main window: conversation view, prompt field, send buttons and menus."""

from pathlib import Path

import wx

from wxclaude.core.claude.claude_files import DiskClaudeFiles
from wxclaude.core.claude.claude_settings import ToolSettings
from wxclaude.core.claude.runner import ClaudeRunner
from wxclaude.core.claude.usage import UsageTracker
from wxclaude.core.config.agents import Agent
from wxclaude.core.config.settings import Settings
from wxclaude.core.config.shortcuts import (
    SEND_ALTERNATIVE_COMMAND,
    SEND_COMMAND,
    ConfigurableCommand,
)
from wxclaude.core.errors import ClaudeSettingsError, SettingsError
from wxclaude.i18n import _
from wxclaude.presenters.conversation_presenter import ConversationLinks, ConversationPresenter
from wxclaude.presenters.file_presenter import FilePresenter
from wxclaude.presenters.message_presenter import MessagePresenter
from wxclaude.presenters.run_presenter import RunLinks, RunPresenter
from wxclaude.presenters.search_presenter import SearchPresenter
from wxclaude.presenters.shared import Shared
from wxclaude.presenters.workspace_presenter import WorkspaceLinks, WorkspacePresenter
from wxclaude.ui.conversation_screen import WxConversationScreen
from wxclaude.ui.conversation_view import ConversationView
from wxclaude.ui.feedback import Feedback
from wxclaude.ui.file_view import WxFileView
from wxclaude.ui.main_menu import MainMenu, MenuHandlers
from wxclaude.ui.message_view import WxMessageView
from wxclaude.ui.preferences_dialog import PreferencesDialog
from wxclaude.ui.run_view import WxRunView
from wxclaude.ui.search_view import WxSearchView
from wxclaude.ui.shortcut_keys import shortcut_from_event
from wxclaude.ui.workspace_settings_dialog import WorkspaceSettingsDialog
from wxclaude.ui.workspace_view import WxWorkspaceView

_POSITION_WIDTH = 150
_STEP_WIDTH = 260


class MainWindow(wx.Frame):
    """Top-level window: the conversation, the prompt, the menus, and what links them."""

    def __init__(self, settings: Settings, runner: ClaudeRunner | None = None) -> None:
        super().__init__(None, title=_("WxClaude"), size=wx.Size(900, 650))
        self._settings = settings
        self._closing = False
        self._usage = UsageTracker()  # gauges and spending, fed by the answers
        runner = runner or ClaudeRunner()
        # Sessions, tasks, plans, rules of Claude Code (a session is renamed through the runner).
        self._files_of_claude = DiskClaudeFiles(runner)
        self._shared = Shared(settings, self._usage, self._files_of_claude)
        self._create_helpers()
        self._build_panel(runner)
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
        self._files = FilePresenter(WxFileView(self, self._feedback))
        self._workspaces = WorkspacePresenter(
            WxWorkspaceView(self, self._feedback),
            self._settings,
            WorkspaceLinks(
                close_conversation=lambda: self._conversations.close(),
                select_conversation=lambda folder: self._conversations.select_in_workspace(folder),
                changed=lambda: self._workspace_changed(),
                save_settings=lambda: self._save_settings(),
            ),
            self._files_of_claude,
        )
        self._actions = MessagePresenter(
            WxMessageView(
                self, self._feedback, lambda message: self._conversation.exchange_of(message)
            ),
            lambda: self.conversation_id,
            self._usage,
            self._files_of_claude,
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
        self._search = SearchPresenter(WxSearchView(self._conversation, self._feedback))
        self._run_view = WxRunView(self, self._conversation, self._feedback)
        self._run = RunPresenter(
            self._run_view,
            runner,
            self._shared,
            RunLinks(
                workspace=lambda: self._workspaces.workspace,
                conversation_id=lambda: self.conversation_id,
                conversation_name=lambda: self._conversations.name,
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
        self._conversations = ConversationPresenter(
            WxConversationScreen(self, self._conversation, self._prompt, self._feedback),
            self._shared,
            self._workspaces,
            ConversationLinks(
                state_changed=lambda: self._refresh_enabled(), is_busy=lambda: self._run.busy
            ),
        )

    def open_workspace(self, folder: Path) -> None:
        """Make ``folder`` the working folder; the conversation of another folder is closed."""
        self._workspaces.open(folder)

    def _workspace_changed(self) -> None:
        """A workspace was opened: the title and what is greyed follow."""
        self._conversations.update_title()
        self._refresh_enabled()

    @property
    def conversation_id(self) -> str:
        """Identifier of the current conversation (the session of the Claude Code CLI)."""
        return self._conversations.conversation_id

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
                new_conversation=lambda _event: self._conversations.new(),
                resume_conversation=lambda _event: self._conversations.resume(),
                refresh_conversation=self._on_refresh_conversation,
                rename_conversation=lambda _event: self._conversations.rename(),
                new_branch=lambda _event: self._conversations.new_branch(),
                interrupt=self._on_interrupt,
                update_interrupt=self._on_update_interrupt,
                choose_agent=lambda _event: self._conversations.choose_agent(),
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

    # Conversation ----------------------------------------------------------------------------

    def _refresh_enabled(self) -> None:
        """Grey out what needs a workspace or a conversation that is not there."""
        has_workspace = self._workspaces.workspace is not None
        has_conversation = bool(self.conversation_id)
        self._menu.refresh_enabled(
            has_workspace=has_workspace, has_conversation=has_conversation, busy=self._run.busy
        )
        self._prompt.Enable(has_conversation)

    @property
    def can_send(self) -> bool:
        """Can a prompt be sent now? It needs a conversation, and Claude must not be answering."""
        return bool(self.conversation_id) and not self._run.busy

    def _on_refresh_conversation(self, _event: wx.CommandEvent) -> None:
        self._conversations.refresh()

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
        return self._conversations.agent_for(alternative=alternative)

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
