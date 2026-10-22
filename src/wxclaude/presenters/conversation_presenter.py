"""The current conversation: which one it is, its name and its agent, and the ways to change it
(new, resume, refresh, rename, branch, the agent). A conversation always belongs to a workspace
(``WorkspacePresenter``); see ``docs/interface.md``."""

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Protocol

from wxclaude.core.claude.claude_projects import SessionInfo, choose_conversation
from wxclaude.core.claude.session_reader import Session
from wxclaude.core.config.agents import Agent
from wxclaude.core.config.workspaces import describe
from wxclaude.core.conversation.conversations import branch_name, default_name, new_conversation_id
from wxclaude.core.conversation.messages import Message
from wxclaude.core.errors import JsonStoreError, SessionReadError
from wxclaude.core.speech.announcements import Announce
from wxclaude.i18n import _
from wxclaude.presenters.shared import Shared
from wxclaude.presenters.workspace_presenter import WorkspacePresenter


class ConversationView(Protocol):
    """What the presenter asks of the main window for the conversation."""

    def ask_name(self, title: str, proposal: str) -> str | None:
        """Ask for a conversation name (the proposal selected); None if cancelled."""
        ...

    def ask_agent(self, agent: Agent) -> Agent | None:
        """Let the user modify ``agent``; None if cancelled."""
        ...

    def choose(self, title: str, prompt: str, labels: list[str]) -> int | None:
        """Ask the user to pick one of ``labels``; its index, None if cancelled."""
        ...

    def show_messages(self, messages: list[Message]) -> None:
        """Show ``messages`` in the conversation view (everything is replaced)."""
        ...

    def clear_messages(self) -> None:
        """Empty the conversation view."""
        ...

    def shown_count(self) -> int:
        """How many messages the conversation view shows."""
        ...

    def focus_last_prompt(self) -> None:
        """Give the focus to the conversation view, at the last prompt of the user."""
        ...

    def clear_prompt(self) -> None:
        """Empty the prompt field."""
        ...

    def focus_prompt(self) -> None:
        """Give the focus to the prompt field."""
        ...

    def show_title(self, title: str) -> None:
        """The title of the window."""
        ...

    def say(self, announce: Announce, **values: object) -> None:
        """Announce, where the category of ``announce`` says."""
        ...

    def show_error(self, message: str) -> None:
        """Tell the user that something failed."""
        ...


def session_label(session: SessionInfo) -> str:
    """How a conversation is listed: its title (or the start of its id), then its last use."""
    when = datetime.fromtimestamp(session.last_used).strftime("%Y-%m-%d %H:%M")
    return _("{title} ({when})").format(title=session.title or session.id[:8], when=when)


class ConversationPresenter:
    """The current conversation of the window.

    ``state_changed`` is called when what is greyed may have changed (a conversation appears or
    goes away).
    """

    def __init__(
        self,
        view: ConversationView,
        shared: Shared,
        workspaces: WorkspacePresenter,
        state_changed: Callable[[], None],
    ) -> None:
        self._view = view
        self._settings = shared.settings
        self._usage = shared.usage
        self._files = shared.files
        self._workspaces = workspaces
        self._state_changed = state_changed
        self.conversation_id = ""
        self.name = ""
        self.agent = shared.settings.default_agent  # the main agent of the conversation
        self._branch_count = 0  # branches made from the current conversation

    def agent_for(self, *, alternative: bool) -> Agent:
        """The agent used to send: the conversation's, or the alternative one over it."""
        if alternative:
            return self._settings.alternative_agent.over(self.agent)
        return self.agent

    # Which conversation ----------------------------------------------------------------------

    def start_new(self, name: str) -> None:
        """A new conversation identifier under ``name`` becomes the current one."""
        self._set_conversation(new_conversation_id(), name)

    def close(self) -> None:
        """No conversation is current any more (a conversation belongs to its workspace)."""
        self._view.clear_messages()
        self._view.clear_prompt()
        self.conversation_id = ""
        self.name = ""
        self._branch_count = 0
        self._usage.start_conversation()
        self.update_title()
        self._state_changed()

    def select_in_workspace(self, workspace: Path) -> None:
        """Select the remembered conversation of ``workspace``, else its most recent one.

        A workspace without any conversation stays without: none is created.
        """
        state = self._workspaces.state
        if state is None:
            return
        sessions = self._files.list_sessions(workspace)
        state.forget_missing({session.id for session in sessions})
        chosen = choose_conversation(sessions, state.current_conversation)
        if chosen is not None:
            self._load(chosen)
            return
        # Nothing to talk to: the prompt and the buttons are greyed, the (empty) view says why.
        self._view.focus_last_prompt()
        self._view.say(Announce.NO_CONVERSATION)

    def update_title(self) -> None:
        """Window title: the conversation, the workspace, then the application."""
        parts = [self.name] if self.name else []
        if self._workspaces.workspace is not None:
            parts.append(describe(str(self._workspaces.workspace))[0])
        parts.append(_("WxClaude"))
        self._view.show_title(" - ".join(parts))

    # Commands of the Conversation menu -------------------------------------------------------

    def new(self) -> None:
        """Ask for a name and start a new conversation with the default agent."""
        number = self._settings.conversation_counter
        name = self._view.ask_name(_("New conversation"), default_name(number))
        if name is None:
            return
        self._settings.conversation_counter = number + 1
        self._view.clear_messages()
        self._view.clear_prompt()
        self.agent = self._settings.default_agent
        self._branch_count = 0
        self.start_new(name)
        self._view.focus_prompt()  # enabled by now: there is a conversation

    def resume(self) -> None:
        """Choose one of the conversations Claude Code holds for the workspace and show it."""
        workspace = self._workspaces.workspace
        if workspace is None:
            return
        sessions = self._files.list_sessions(workspace)
        if not sessions:
            self._view.show_error(_("This workspace has no conversation yet."))
            return
        labels = [session_label(session) for session in sessions]
        index = self._view.choose(_("Resume a conversation"), _("Choose a conversation:"), labels)
        if index is not None:
            self._load(sessions[index])

    def refresh(self) -> None:
        """Read the session file again: messages added since (by the CLI) appear."""
        workspace = self._workspaces.workspace
        if workspace is None or not self.conversation_id:
            return
        found = [s for s in self._files.list_sessions(workspace) if s.id == self.conversation_id]
        if not found:
            self._view.say(Announce.CONVERSATION_NOT_SAVED)
            return
        session = self._read(found[0].path)
        if session is None:
            return
        before = self._view.shown_count()
        self._view.show_messages(session.messages)
        self._view.focus_last_prompt()
        added = max(0, self._view.shown_count() - before)
        self._view.say(Announce.CONVERSATION_REFRESHED, count=added)

    def rename(self) -> None:
        name = self._view.ask_name(_("Rename the conversation"), self.name)
        if name is not None:
            self._set_name(name)

    def new_branch(self) -> None:
        # Until --fork-session is used a branch keeps the text on screen under a new name.
        proposal = branch_name(self.name, self._branch_count + 1)
        name = self._view.ask_name(_("New conversation branch"), proposal)
        if name is None:
            return
        self._branch_count = 0  # the new branch starts its own numbering
        self.start_new(name)  # a branch is a session of its own

    def choose_agent(self) -> None:
        agent = self._view.ask_agent(self.agent)
        if agent is not None:
            self.agent = agent
            self._remember()

    # What is kept ----------------------------------------------------------------------------

    def _set_conversation(self, conversation_id: str, name: str) -> None:
        """Make the conversation ``conversation_id`` the current one and remember it."""
        if conversation_id != self.conversation_id:
            self._usage.start_conversation()
        self.conversation_id = conversation_id
        self._set_name(name)  # also remembers the conversation
        self._state_changed()

    def _set_name(self, name: str) -> None:
        self.name = name
        self._remember()
        self.update_title()

    def _remember(self) -> None:
        """Keep what is remembered of the workspace: its current conversation, the name and the
        main agent of that conversation."""
        state = self._workspaces.state
        if not self.conversation_id or state is None:
            return
        state.remember(self.conversation_id, self.name, self.agent)
        try:
            state.save()
        except JsonStoreError as error:
            self._view.show_error(_("Cannot save the workspace data.\n{error}").format(error=error))

    def _load(self, chosen: SessionInfo) -> bool:
        """Show the conversation ``chosen`` and make it current; False if it cannot be read."""
        session = self._read(chosen.path)
        if session is None:
            return False
        settings = self._settings
        state = self._workspaces.state
        record = state.conversations.get(chosen.id) if state is not None else None
        name = (record.name if record else "") or chosen.title
        if not name:
            name = default_name(settings.conversation_counter)
            settings.conversation_counter += 1
        # A conversation WxClaude knows nothing about takes the agent of its last message as its
        # main agent (it is remembered by _set_conversation below).
        known = record.agent if record else session.last_agent
        self.agent = known.over(settings.default_agent)
        self._view.show_messages(session.messages)
        self._view.clear_prompt()
        self._branch_count = 0
        self._set_conversation(chosen.id, name)
        self._view.focus_last_prompt()
        return True

    def _read(self, path: Path) -> Session | None:
        try:
            return self._files.read_session(path)
        except SessionReadError as error:
            self._view.show_error(_("Cannot read the conversation.\n{error}").format(error=error))
            return None
