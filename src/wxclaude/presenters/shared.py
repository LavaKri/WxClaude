"""What several presenters share: the settings, the usage of Claude, the files of Claude Code and
the trust state of the workspace; and what they do the same way."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from wxclaude.core.claude.claude_files import ClaudeFiles
from wxclaude.core.claude.session_reader import Session
from wxclaude.core.claude.usage import UsageTracker
from wxclaude.core.config.agents import Agent
from wxclaude.core.config.providers import ProviderStore
from wxclaude.core.config.settings import Settings
from wxclaude.core.errors import SessionReadError
from wxclaude.core.security.key_relay import KeyRelay
from wxclaude.i18n import _
from wxclaude.presenters.security_presenter import SecurityPresenter


@dataclass(frozen=True, slots=True)
class Shared:
    """The objects of the model the presenters of one window work on together."""

    settings: Settings
    usage: UsageTracker
    files: ClaudeFiles
    security: SecurityPresenter | None = None  # None: no trust state (tests)
    providers: ProviderStore | None = None  # None: Claude only (tests)
    relay: KeyRelay | None = None  # holds the keys for the transmission Relayed (None: tests)


@dataclass(slots=True)
class ConversationState:
    """Which conversation is the current one. ``ConversationPresenter`` owns it and changes it;
    ``ConversationLoader`` reads it, and changes the agent and the branches when it shows another
    conversation."""

    agent: Agent  # the main agent of the conversation
    conversation_id: str = ""
    name: str = ""
    fork_from: str = ""  # the conversation a branch comes from, until its first message
    branch_count: int = 0  # branches made from the current conversation


def read_session(
    files: ClaudeFiles, path: Path, show_error: Callable[[str], None]
) -> Session | None:
    """The session file at ``path``; None, with the error shown, if it cannot be read."""
    try:
        return files.read_session(path)
    except SessionReadError as error:
        show_error(_("Cannot read the conversation.\n{error}").format(error=error))
        return None
