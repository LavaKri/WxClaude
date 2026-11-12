"""Showing the conversations that Claude Code holds for a workspace: the one selected when a
workspace is opened, one resumed from a list, the current one read again.

Taken out of ``ConversationPresenter``. Making a conversation the current one (what is
remembered, the title, what is greyed) stays there: it is given here as ``make_current``.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from wxclaude.core.claude.claude_projects import SessionInfo, choose_conversation
from wxclaude.core.conversation.messages import Message
from wxclaude.core.speech.announcements import Announce
from wxclaude.i18n import _
from wxclaude.presenters.shared import ConversationState, Shared, read_session
from wxclaude.presenters.workspace_presenter import WorkspacePresenter


class LoaderView(Protocol):
    """What the loader asks of the interface."""

    def choose(self, title: str, prompt: str, labels: list[str]) -> int | None:
        """Ask the user to pick one of ``labels``; its index, None if cancelled."""
        ...

    def show_messages(self, messages: list[Message]) -> None:
        """Show ``messages`` in the conversation view (everything is replaced)."""
        ...

    def shown_count(self) -> int:
        """How many messages the conversation view shows."""
        ...

    def clear_prompt(self) -> None:
        """Empty the prompt field."""
        ...

    def focus_last_prompt(self) -> None:
        """Give the focus to the conversation view, at the last prompt of the user."""
        ...

    def say(self, announce: Announce, **values: object) -> None:
        """Announce, where the category of ``announce`` says."""
        ...

    def set_status(self, text: str) -> None:
        """The message field of the status bar."""
        ...

    def show_error(self, message: str) -> None:
        """Tell the user that something failed."""
        ...


def session_label(session: SessionInfo) -> str:
    """How a conversation is listed: its title (or the start of its id), then its last use."""
    when = datetime.fromtimestamp(session.last_used).strftime("%Y-%m-%d %H:%M")
    return _("{title} ({when})").format(title=session.title or session.id[:8], when=when)


@dataclass(frozen=True, slots=True)
class LoaderLinks:
    """What the loader asks of ``ConversationPresenter``: ``make_current(id, name, session_total)``
    makes a conversation the current one, ``set_name(name)`` names the current one anew."""

    make_current: Callable[[str, str, float | None], None]
    set_name: Callable[[str], None]


class ConversationLoader:
    """Selects, resumes and refreshes conversations."""

    def __init__(
        self,
        view: LoaderView,
        shared: Shared,
        workspaces: WorkspacePresenter,
        current: ConversationState,
        links: LoaderLinks,
    ) -> None:
        self._view = view
        self._settings = shared.settings
        self._usage = shared.usage
        self._files = shared.files
        self._workspaces = workspaces
        self._current = current
        self._links = links

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
        if index is not None and self._load(sessions[index]):
            self._view.set_status(self._usage.ready_line())

    def refresh(self) -> None:
        """Read the session file again: messages added since (by the CLI) appear."""
        workspace = self._workspaces.workspace
        current = self._current
        if workspace is None or not current.conversation_id:
            return
        found = [s for s in self._files.list_sessions(workspace) if s.id == current.conversation_id]
        if not found:
            self._view.say(Announce.CONVERSATION_NOT_SAVED)
            return
        session = read_session(self._files, found[0].path, self._view.show_error)
        if session is None:
            return
        if session.title and session.title != current.name:
            self._links.set_name(session.title)  # renamed elsewhere (the CLI, another window)
        if session.total_cost_usd is not None:
            self._usage.session_total = session.total_cost_usd  # it may have grown elsewhere
        before = self._view.shown_count()
        self._view.show_messages(session.messages)
        self._view.focus_last_prompt()
        added = max(0, self._view.shown_count() - before)
        self._view.say(Announce.CONVERSATION_REFRESHED, count=added)

    def _load(self, chosen: SessionInfo) -> bool:
        """Show the conversation ``chosen`` and make it current; False if it cannot be read."""
        session = read_session(self._files, chosen.path, self._view.show_error)
        if session is None:
            return False
        state = self._workspaces.state
        record = state.conversations.get(chosen.id) if state is not None else None
        # A conversation WxClaude knows nothing about takes the agent of its last message as its
        # main agent (it is remembered by ``make_current`` below).
        known = record.agent if record else session.last_agent
        self._current.agent = known.over(self._settings.default_agent)
        self._view.show_messages(session.messages)
        self._view.clear_prompt()
        self._current.branch_count = 0
        self._links.make_current(chosen.id, session.title or chosen.id[:8], session.total_cost_usd)
        self._view.focus_last_prompt()
        return True
