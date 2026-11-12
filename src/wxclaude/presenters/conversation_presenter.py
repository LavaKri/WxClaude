"""The current conversation: which one it is, its name and its agent, and the ways to change it
(new, resume, refresh, rename, branch, delete, the agent). A conversation always belongs to a
workspace (``WorkspacePresenter``); see ``docs/interface.md``."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from wxclaude.core.config.agents import Agent
from wxclaude.core.config.workspace_state import WorkspaceState
from wxclaude.core.config.workspaces import describe
from wxclaude.core.conversation.conversations import branch_name, default_name, new_conversation_id
from wxclaude.core.conversation.messages import Message
from wxclaude.core.errors import (
    ClaudeNotFoundError,
    JsonStoreError,
    RunnerError,
)
from wxclaude.core.speech.announcements import Announce
from wxclaude.i18n import _
from wxclaude.presenters.conversation_loader import ConversationLoader, LoaderLinks
from wxclaude.presenters.shared import ConversationState, Shared
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

    def set_status(self, text: str) -> None:
        """The message field of the status bar."""
        ...

    def show_error(self, message: str) -> None:
        """Tell the user that something failed."""
        ...

    def confirm(self, title: str, message: str) -> bool:
        """Ask a Yes / No question (No by default); True for Yes."""
        ...

    def move_to_recycle_bin(self, paths: list[Path]) -> bool:
        """Move ``paths`` to the Recycle Bin; False if one of them could not be moved."""
        ...


@dataclass(frozen=True, slots=True)
class ConversationLinks:
    """What the presenter asks of the window: ``state_changed`` is called when what is greyed may
    have changed (a conversation appears or goes away), ``is_busy`` tells whether Claude is
    answering, and ``start`` starts Claude on a message with an agent (False if it could not)."""

    state_changed: Callable[[], None]
    is_busy: Callable[[], bool]
    start: Callable[[str, Agent], bool]
    entered: Callable[[str], None] = lambda name: None  # a conversation became the current one
    remote: Callable[[], bool] = lambda: False  # is the remote control on? the title says it


class ConversationPresenter:
    """The current conversation of the window.

    Its name is the one of its session, kept by the CLI (``--name`` with the first message,
    ``/rename`` afterwards): until the first message there is no session and the name only lives
    here. A branch is the same: until its first message it is only ``fork_from``, the conversation
    whose history that message copies.
    """

    def __init__(
        self,
        view: ConversationView,
        shared: Shared,
        workspaces: WorkspacePresenter,
        links: ConversationLinks,
    ) -> None:
        self._view = view
        self._settings = shared.settings
        self._usage = shared.usage
        self._files = shared.files
        self._security = shared.security
        self._workspaces = workspaces
        self._links = links
        self._current = ConversationState(agent=shared.settings.default_agent)
        self._loader = ConversationLoader(
            view,
            shared,
            workspaces,
            self._current,
            LoaderLinks(self._set_conversation, self._set_name),
        )

    @property
    def conversation_id(self) -> str:
        return self._current.conversation_id

    @property
    def name(self) -> str:
        return self._current.name

    @property
    def fork_from(self) -> str:
        """The conversation a branch comes from, until its first message."""
        return self._current.fork_from

    @property
    def agent(self) -> Agent:
        """The main agent of the conversation."""
        return self._current.agent

    @agent.setter
    def agent(self, agent: Agent) -> None:
        self._current.agent = agent

    def agent_for(self, *, alternative: bool) -> Agent:
        """The agent used to send: the conversation's, or the alternative one of the workspace
        (the one of the Preferences without a workspace); a field it leaves out comes from the
        conversation's agent."""
        if alternative:
            return self.workspace_alternative_agent.over(self.agent)
        return self.agent

    @property
    def workspace_alternative_agent(self) -> Agent:
        """The alternative agent of the workspace (the Preferences' one without a workspace)."""
        state = self._workspaces.state
        return self._settings.alternative_agent if state is None else state.alternative_agent

    # Sending ---------------------------------------------------------------------------------

    @property
    def has_conversation(self) -> bool:
        """Is there a current conversation? (Not before one is started or opened.)"""
        return bool(self.conversation_id)

    @property
    def can_send(self) -> bool:
        """Can a message be sent now? It needs a conversation, and Claude must not be answering."""
        return self.has_conversation and not self._links.is_busy()

    def send(self, text: str, *, alternative: bool) -> None:
        """Send what was typed with the agent of the conversation, or with the alternative one.
        Nothing is sent when the text is blank or a message cannot be sent now. Once Claude is
        started the prompt is emptied and the focus goes to the message that was just sent;
        otherwise the prompt keeps its text."""
        text = text.strip()
        if not text or not self.can_send:
            return
        if self._links.start(text, self.agent_for(alternative=alternative)):
            self._view.clear_prompt()
            self._view.focus_last_prompt()

    # Which conversation ----------------------------------------------------------------------

    def start_new(self, name: str, session_total: float | None = 0.0) -> None:
        """A new conversation identifier under ``name`` becomes the current one.

        ``session_total`` is what the CLI has already counted for its session (see
        ``UsageTracker.start_conversation``): nothing for a conversation that is really new.
        """
        self._set_conversation(new_conversation_id(), name, session_total)

    def close(self) -> None:
        """No conversation is current any more (a conversation belongs to its workspace)."""
        self._view.clear_messages()
        self._start_over()
        current = self._current
        current.conversation_id = ""
        current.name = ""
        current.fork_from = ""
        self._usage.start_conversation()
        self.update_title()
        self._links.state_changed()

    def select_in_workspace(self, workspace: Path) -> None:
        """Select the remembered conversation of ``workspace``, else its most recent one (see
        ``ConversationLoader``). A workspace without any conversation stays without."""
        self._loader.select_in_workspace(workspace)

    def update_title(self) -> None:
        """Window title: the conversation, the workspace, then the application. With the remote
        control on, it starts with that, so that the screen reader says it first."""
        parts = [_("Remote enabled")] if self._links.remote() else []
        if self.name:
            parts.append(self.name)
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
        self._start_over()
        self._current.agent = self._settings.default_agent
        self.start_new(name)
        self._view.set_status(self._usage.ready_line())  # replaces a message such as a deletion
        self._view.focus_prompt()  # enabled by now: there is a conversation

    def resume(self) -> None:
        """Choose one of the conversations Claude Code holds for the workspace and show it."""
        self._loader.resume()

    def refresh(self) -> None:
        """Read the session file again: messages added since (by the CLI) appear."""
        self._loader.refresh()

    def rename(self) -> None:
        """Ask for a name; a conversation that has a session is renamed by the CLI itself."""
        workspace = self._workspace_with_conversation()
        if workspace is None or self._busy_reported(
            _("Wait for Claude to finish before renaming the conversation.")
        ):
            return
        name = self._view.ask_name(_("Rename the conversation"), self.name)
        if name is None or name == self.name:
            return
        if self._files.find_session(self.conversation_id) is not None:
            try:
                self._files.rename_session(
                    self.conversation_id,
                    name,
                    workspace,
                    restricted=self._security is not None and self._security.restricted,
                )
            except (ClaudeNotFoundError, RunnerError) as error:
                self._view.show_error(
                    _("The conversation could not be renamed.\n{error}").format(error=error)
                )
                return
        self._set_name(name)

    def new_branch(self) -> None:
        """Ask for a name and make a branch of the conversation the current one.

        The text on screen stays: the first message of the branch copies the history of the
        conversation into a session of its own (``--fork-session``), the original is left as it is.
        """
        parent = self.conversation_id
        if not parent:
            return
        if self._files.find_session(parent) is None:
            self._view.show_error(
                _("This conversation has no message yet: there is nothing to branch.")
            )
            return
        proposal = branch_name(self.name, self._current.branch_count + 1)
        name = self._view.ask_name(_("New conversation branch"), proposal)
        if name is None:
            return
        self._current.branch_count = 0  # the new branch starts its own numbering
        # A branch is a session of its own, whose total starts from the one of its parent.
        self.start_new(name, self._usage.session_total)
        self._current.fork_from = parent
        self._view.focus_last_prompt()

    def delete(self) -> None:
        """After a confirmation, move the conversation to the Recycle Bin (what Claude Code keeps
        of it), then select the most recent conversation left in the workspace."""
        workspace = self._workspace_with_conversation()
        if workspace is None or self._busy_reported(
            _("Wait for Claude to finish before deleting the conversation.")
        ):
            return
        question = _('Move the conversation "{name}" to the Recycle Bin?').format(name=self.name)
        if not self._view.confirm(_("Delete the conversation"), question):
            return
        if not self._view.move_to_recycle_bin(self._files.session_paths(self.conversation_id)):
            self._view.show_error(_("The conversation could not be moved to the Recycle Bin."))
            return
        name = self.name
        self.close()
        self._view.say(Announce.CONVERSATION_DELETED, name=name)
        self.select_in_workspace(workspace)  # the deleted one is forgotten there

    def choose_agent(self) -> None:
        agent = self._view.ask_agent(self.agent)
        if agent is not None:
            self.agent = agent
            self._remember()

    def set_workspace_alternative_agent(self, agent: Agent) -> None:
        """Remember the fields of the alternative agent that this workspace sets."""
        state = self._workspaces.state
        if state is None or state.alternative_agent == agent:
            return
        state.alternative_agent = agent
        self._save_state(state)

    # What is kept ----------------------------------------------------------------------------

    def _set_conversation(
        self, conversation_id: str, name: str, session_total: float | None = None
    ) -> None:
        """Make the conversation ``conversation_id`` the current one and remember it."""
        changed = conversation_id != self.conversation_id
        if changed:
            self._usage.start_conversation(session_total)
        elif session_total is not None:
            self._usage.session_total = session_total
        self._current.conversation_id = conversation_id
        self._current.name = name
        self._current.fork_from = ""
        self._remember()
        self.update_title()
        self._links.state_changed()
        if changed:
            self._links.entered(name)

    def _set_name(self, name: str) -> None:
        self._current.name = name
        self.update_title()

    def _remember(self) -> None:
        """Keep what is remembered of the workspace: its current conversation and the main agent
        of that conversation."""
        state = self._workspaces.state
        if not self.conversation_id or state is None:
            return
        state.remember(self.conversation_id, self.agent)
        self._save_state(state)

    def _save_state(self, state: WorkspaceState) -> None:
        try:
            state.save()
        except JsonStoreError as error:
            self._view.show_error(_("Cannot save the workspace data.\n{error}").format(error=error))

    def _start_over(self) -> None:
        """Another conversation is going to be shown: its prompt is empty, and its branches are
        counted again."""
        self._view.clear_prompt()
        self._current.branch_count = 0

    def _workspace_with_conversation(self) -> Path | None:
        """The workspace, when there is a conversation in it to work on; else None."""
        workspace = self._workspaces.workspace
        return workspace if workspace is not None and self.has_conversation else None

    def _busy_reported(self, message: str) -> bool:
        """Is Claude answering? Then ``message`` is shown and the command must do nothing."""
        busy = self._links.is_busy()
        if busy:
            self._view.show_error(message)
        return busy
