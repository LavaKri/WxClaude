"""Main window: conversation view, prompt field, send buttons and menus."""

from pathlib import Path

import wx

from wxclaude.core.claude.auth import ClaudeLogin
from wxclaude.core.claude.claude_files import DiskClaudeFiles
from wxclaude.core.claude.runner import ClaudeRunner
from wxclaude.core.claude.status import read_status
from wxclaude.core.claude.usage import UsageTracker
from wxclaude.core.config.agents import Agent
from wxclaude.core.config.providers import ProviderStore
from wxclaude.core.config.settings import Settings
from wxclaude.core.errors import RemoteError, SettingsError
from wxclaude.core.security.key_relay import KeyRelay
from wxclaude.core.security.vault import DpapiVault
from wxclaude.i18n import _
from wxclaude.presenters.claude_check import ClaudeCheck
from wxclaude.presenters.conversation_presenter import ConversationLinks, ConversationPresenter
from wxclaude.presenters.file_presenter import FilePresenter
from wxclaude.presenters.message_presenter import MessagePresenter
from wxclaude.presenters.remote_presenter import RemoteLinks
from wxclaude.presenters.run_presenter import RunLinks, RunPresenter
from wxclaude.presenters.search_presenter import SearchPresenter
from wxclaude.presenters.security_presenter import SecurityPresenter
from wxclaude.presenters.shared import Shared
from wxclaude.presenters.usage_presenter import UsagePresenter
from wxclaude.presenters.workspace_presenter import WorkspaceLinks, WorkspacePresenter
from wxclaude.presenters.workspace_settings_presenter import (
    WorkspaceSettingsLinks,
    WorkspaceSettingsPresenter,
)
from wxclaude.ui.claude_check_view import WxClaudeCheckView
from wxclaude.ui.conversation_screen import WxConversationScreen
from wxclaude.ui.conversation_view import ConversationView
from wxclaude.ui.display_options import DisplayOptions
from wxclaude.ui.feedback import Feedback
from wxclaude.ui.file_view import WxFileView
from wxclaude.ui.focus_keeper import FocusKeeper
from wxclaude.ui.gauge_watch import GaugeWatch
from wxclaude.ui.history_dialog import show_history
from wxclaude.ui.login_dialog import LoginDialog
from wxclaude.ui.main_menu import MainMenu, MenuHandlers
from wxclaude.ui.message_view import WxMessageView
from wxclaude.ui.preferences_dialog import PreferencesDialog
from wxclaude.ui.prompt_area import PromptActions, PromptArea
from wxclaude.ui.remote_control import RemoteControl
from wxclaude.ui.run_view import WxRunView
from wxclaude.ui.search_view import WxSearchView
from wxclaude.ui.security_view import WxSecurityView
from wxclaude.ui.usage_view import WxUsageView
from wxclaude.ui.workspace_settings_view import WxWorkspaceSettingsView
from wxclaude.ui.workspace_view import WxWorkspaceView

_POSITION_WIDTH = 150
_STEP_WIDTH = 260


class MainWindow(wx.Frame):
    """Top-level window: the conversation, the prompt, the menus, and what links them."""

    def __init__(
        self,
        settings: Settings,
        runner: ClaudeRunner | None = None,
        remote_pipe: str | None = None,
    ) -> None:
        """``remote_pipe`` is the name of the pipe of the remote control, None when it is off."""
        super().__init__(None, title=_("WxClaude"), size=wx.Size(900, 650))
        self._settings = settings
        self._closing = False
        self._remote: RemoteControl | None = None
        # Reads the gauges now and every minute once started (by the application, not the tests).
        self.gauge_watch = GaugeWatch(
            self, lambda now: self._run.refresh_gauges_if_due(now), lambda: self._closing
        )
        self._usage = UsageTracker()  # gauges and spending, fed by the answers
        runner = runner or ClaudeRunner()
        # Sessions, tasks, plans, rules of Claude Code (a session is renamed through the runner).
        self._files_of_claude = DiskClaudeFiles(runner)
        self._create_helpers()
        self._build_panel(runner)
        self._build_menu_bar()
        # The position in the conversation, the step of Claude, then the messages.
        status_bar = self.CreateStatusBar(3)
        status_bar.SetStatusWidths([_POSITION_WIDTH, _STEP_WIDTH, -1])
        self._feedback.set_status(_("Ready"))
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self._focus_keeper = FocusKeeper(  # Alt+Tab away and back
            self, lambda: self._closing, self._default_focus
        )
        if settings.maximize_at_start:
            self.Maximize()
        self._display = DisplayOptions(
            self._conversation, self._menu, self._settings, lambda: self._save_settings()
        )
        self._apply_settings()
        self._refresh_enabled()
        self._menu.refresh_recent()
        self._start_remote(remote_pipe)
        self._workspaces.restore_last_session()
        wx.CallAfter(self._check_claude_at_start)
        wx.CallAfter(self._focus_main_field)
        if settings.load_warning:
            wx.CallAfter(self._feedback.show_file_warning, settings.load_warning)
        if self.providers.warning:
            wx.CallAfter(self._feedback.show_file_warning, self.providers.warning)

    def _create_helpers(self) -> None:
        """The objects that do the work for the window. The window's own methods are looked up at
        each call, so that they can be replaced."""
        self._feedback = Feedback(self, lambda: self._closing, self._settings.destination_for)
        self._security = SecurityPresenter(WxSecurityView(self, self._feedback))
        self.providers = ProviderStore.load(self._settings.providers_path, DpapiVault())
        self._relay = KeyRelay(  # holds the keys of the providers for the transmission Relayed
            idle_seconds=self._settings.relay_idle_minutes * 60,
            timeout=self._settings.relay_timeout_seconds,
        )
        self._shared = Shared(
            self._settings,
            self._usage,
            self._files_of_claude,
            self._security,
            self.providers,
            self._relay,
        )
        self._files = FilePresenter(WxFileView(self, self._feedback))
        self._workspaces = WorkspacePresenter(
            WxWorkspaceView(self, self._feedback),
            self._settings,
            WorkspaceLinks(
                close_conversation=lambda: self._conversations.close(),
                select_conversation=lambda folder: self._conversations.select_in_workspace(folder),
                changed=lambda: self._workspace_changed(),
                save_settings=lambda: self._save_settings(),
                opened=lambda: wx.CallAfter(self._greet_folder),  # once the window shows
                entered=lambda name: self._feedback.note_workspace(name),
            ),
            self._files_of_claude,
            self._security,
        )
        self._workspace_settings = WorkspaceSettingsPresenter(
            WxWorkspaceSettingsView(self, self._feedback, self._security, self.providers),
            self._settings,
            self._security,
            WorkspaceSettingsLinks(
                workspace=lambda: self._workspaces.workspace,
                alternative_agent=lambda: self._conversations.workspace_alternative_agent,
                set_alternative_agent=lambda agent: (
                    self._conversations.set_workspace_alternative_agent(agent)
                ),
            ),
        )
        self._actions = MessagePresenter(
            WxMessageView(
                self, self._feedback, lambda message: self._conversation.exchange_of(message)
            ),
            lambda: self.conversation_id,
            self._files_of_claude,
        )
        self._usage_dialogs = UsagePresenter(
            WxUsageView(self, self._feedback),
            self._usage,
            lambda: self._workspaces.stats,
            self.providers,
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
                fork_from=lambda: self._conversations.fork_from,
                stats=lambda: self._workspaces.stats,
                is_closing=lambda: self._closing,
                state_changed=lambda: self._refresh_enabled(),
            ),
        )
        self._claude_check = ClaudeCheck(
            runner,
            lambda: self._usage.ready_line(),
            WxClaudeCheckView(
                self._feedback,
                lambda: self._open_preferences(claude_page=True),
                self._open_sign_in,
                lambda: not self._closing and bool(self),  # bool: False once wx deleted it
            ),
            # The login of Claude only matters when the messages go to Claude itself.
            lambda: self.providers.get(self._settings.default_agent.provider).is_builtin,
        )
        self._prompt_area = PromptArea(
            panel,
            PromptActions(
                send=lambda alternative: self.send_prompt(alternative=alternative),
                interrupt=lambda: self._run.interrupt(),
                choose_agent=lambda: self._conversations.choose_agent(),
                can_send=lambda: self.can_send,
                can_interrupt=lambda: self._run.busy,
            ),
            self._settings.shortcut_for,
        )
        self._prompt = self._prompt_area.field

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(conversation_label, 0, wx.LEFT | wx.TOP, 6)
        sizer.Add(self._conversation, 3, wx.EXPAND | wx.ALL, 6)
        self._prompt_area.add_to(sizer)
        panel.SetSizer(sizer)
        self._conversations = ConversationPresenter(
            WxConversationScreen(
                self, self._conversation, self._prompt, self._feedback, self.providers
            ),
            self._shared,
            self._workspaces,
            ConversationLinks(
                state_changed=lambda: self._refresh_enabled(),
                is_busy=lambda: self._run.busy,
                start=lambda text, agent: self._run.start(text, agent),
                entered=lambda name: self._feedback.note_conversation(name),
                remote=lambda: self._remote is not None,
            ),
        )

    def open_workspace(self, folder: Path) -> None:
        """Make ``folder`` the working folder; the conversation of another folder is closed."""
        self._workspaces.open(folder)

    def _workspace_changed(self) -> None:
        """A workspace was opened: the title and what is greyed follow."""
        self._conversations.update_title()
        self._refresh_enabled()
        self.gauge_watch.check()  # a first workspace: the gauges may not be known yet

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
                export=lambda _event: self._files.export(self._conversation.markdown_text()),
                quit=lambda _event: self.Close(),
                new_conversation=lambda _event: self._conversations.new(),
                resume_conversation=lambda _event: self._conversations.resume(),
                refresh_conversation=self._on_refresh_conversation,
                rename_conversation=lambda _event: self._conversations.rename(),
                new_branch=lambda _event: self._conversations.new_branch(),
                delete_conversation=lambda _event: self._conversations.delete(),
                toggle_tools_summary=lambda event: self._display.set_tools_summary(
                    event.IsChecked()
                ),
                toggle_marks=lambda event: self._display.set_without_marks(event.IsChecked()),
                interrupt=self._on_interrupt,
                update_interrupt=self._on_update_interrupt,
                choose_agent=lambda _event: self._conversations.choose_agent(),
                find=lambda _event: search.find(),
                find_next=lambda _event: search.find_next(),
                find_previous=lambda _event: search.find_previous(),
                tasks=lambda _event: self._actions.show_tasks(),
                plans=lambda _event: self._actions.show_plans(),
                usage=lambda _event: self._usage_dialogs.show_gauges(),
                statistics=lambda _event: self._usage_dialogs.show_statistics(),
                sign_in=self._on_sign_in,
                open_workspace_folder=lambda _event: self._files.open_folder(
                    self._workspaces.workspace
                ),
                workspace_settings=self._on_workspace_settings,
                preferences=self._on_preferences,
                show_help=lambda _event: self._files.show_help(self._settings.language),
                about=lambda _event: self._files.about(),
                history=lambda _event: show_history(self, self._feedback),
                open_log_folder=lambda _event: self._files.open_folder(self._settings.log_dir),
                recent_workspaces=lambda: self._workspaces.recent(),
                open_recent=lambda folder: self._workspaces.open_recent(folder),
            ),
        )

    def _apply_settings(self) -> None:
        """Bring the window in line with the settings: at the start, and after the Preferences.
        The shortcuts are shown (and activated) in the menus and in the labels of the send
        buttons."""
        self._feedback.apply_screen_reader_output(self._settings.screen_reader_output)
        self._display.apply()
        self._menu.apply_shortcuts(self._settings.shortcut_for)
        self._prompt_area.apply_shortcuts()
        self._apply_claude_path()

    # Conversation ----------------------------------------------------------------------------

    def _refresh_enabled(self) -> None:
        """Grey out what needs a workspace or a conversation that is not there."""
        has_workspace = self._workspaces.workspace is not None
        has_conversation = self._conversations.has_conversation
        self._menu.refresh_enabled(
            has_workspace=has_workspace,
            has_conversation=has_conversation,
            busy=self._run.busy,
            refreshing=self._run.refreshing,
        )
        self._prompt.Enable(has_conversation)

    @property
    def can_send(self) -> bool:
        """Can a prompt be sent now? It needs a conversation, and Claude must not be answering."""
        return self._conversations.can_send

    def _on_refresh_conversation(self, _event: wx.CommandEvent) -> None:
        self._conversations.refresh()

    def _on_preferences(self, _event: wx.CommandEvent) -> None:
        self._open_preferences(claude_page=False)

    def _open_preferences(self, *, claude_page: bool) -> None:
        with PreferencesDialog(self, self._settings, self.providers) as dialog:
            if claude_page:
                dialog.show_claude_page()
            if self._feedback.modal(dialog) == wx.ID_OK:
                dialog.apply(self._settings)
                self._apply_settings()
                self._claude_check.check(offer=False)
                self._save_settings()

    def _check_claude_at_start(self) -> None:
        """Once the window is up: Claude Code missing is said now, not at the first message."""
        if not self._closing:
            self._claude_check.check(offer=True)

    def _default_focus(self) -> wx.Window:
        """Where the focus goes when the control it was on cannot take it again (focus.md, rule E):
        the prompt when it can be typed in, else the conversation view."""
        return self._prompt if self._prompt.IsEnabled() else self._conversation

    def _focus_main_field(self) -> None:
        """At startup the focus is on the conversation view, at the last prompt if there is one."""
        self._conversation.focus_last_prompt()

    # Prompt ----------------------------------------------------------------------------------

    def agent_for(self, *, alternative: bool) -> Agent:
        """The agent used to send: the conversation's, or the alternative one over it."""
        return self._conversations.agent_for(alternative=alternative)

    def send_prompt(self, *, alternative: bool) -> None:
        """Send the prompt with the conversation's agent, or with the alternative agent."""
        self._conversations.send(self._prompt.GetValue(), alternative=alternative)

    def _start_remote(self, pipe: str | None) -> None:
        """The remote control (``--remote``): create the pipe, and the title says it is on. If the
        pipe cannot be created the application goes on without it, and says so."""
        if pipe is None:
            return
        control = RemoteControl(
            pipe,
            RemoteLinks(
                has_conversation=lambda: self._conversations.has_conversation,
                busy=lambda: self._run.busy,
                answering=lambda: self._run.answering,
                interrupt=lambda: self._run.interrupt(),
                send=lambda text: self._run.start(text, self.agent_for(alternative=False)),
                messages=lambda: self._conversation.messages,
                announcements=lambda: self._feedback.announcements.history.lines(),
            ),
        )
        try:
            control.start()
        except RemoteError as error:
            message = _("The remote control cannot start.\n{error}").format(error=error)
            wx.CallAfter(self._feedback.show_error, message)
            return
        self._remote = control
        self._conversations.update_title()

    def _on_workspace_settings(self, _event: wx.CommandEvent) -> None:
        self._workspace_settings.edit()

    def _greet_folder(self) -> None:
        """The workspace opened: offer to approve it, or say what changed in it. The folder is
        restricted until then, so a message sent meanwhile is safe."""
        if not self._closing:
            self._security.greet()

    def _on_sign_in(self, _event: wx.CommandEvent) -> None:
        self._open_sign_in()

    def _open_sign_in(self) -> None:
        """The sign-in dialog, for the claude program chosen in the Preferences. Once it is
        closed the state of the login is asked again (the status bar follows)."""
        path = self._run.claude_path
        with LoginDialog(self, ClaudeLogin(claude_path=path), lambda: read_status(path)) as dialog:
            self._feedback.modal(dialog)
        self._claude_check.check(offer=False)

    def _on_interrupt(self, _event: wx.CommandEvent) -> None:
        self._run.interrupt()

    def _on_update_interrupt(self, event: wx.UpdateUIEvent) -> None:
        event.Enable(self._run.busy)

    # Misc ------------------------------------------------------------------------------------

    def _apply_claude_path(self) -> None:
        """Tell the runner which claude executable to start: the chosen file, or the PATH."""
        settings = self._settings
        self._run.claude_path = "" if settings.claude_auto_search else settings.claude_path

    def _save_settings(self) -> None:
        try:
            self._settings.save()
        except SettingsError as error:
            self._feedback.show_error(_("Cannot save the settings.\n{error}").format(error=error))

    def _on_close(self, event: wx.CloseEvent) -> None:
        self._closing = True
        self.gauge_watch.stop()
        self._run.stop()
        if self._remote is not None:
            self._remote.stop()  # the pipe is freed
        self._relay.stop()  # the port is closed and the tokens are forgotten
        self._save_settings()
        event.Skip()
