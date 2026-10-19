"""Announcements: what the application says about what it just did.

Every message is a member of ``Announce``. The code only calls ``AnnouncementCenter.notify``; how
a message really reaches the user is the business of the sink the center is connected to (see
``ui/message_sinks.py``), chosen in Options > Screen reader.
"""

import enum
from collections.abc import Callable
from typing import Protocol

from wxclaude.core.errors import ScreenReaderOutputError
from wxclaude.i18n import N_, _


class Announce(enum.Enum):
    """All the messages of the application; the value is a message id (translate, then format)."""

    WORKSPACE_OPENED = N_("Workspace: {folder}")
    NEW_CONVERSATION = N_("New conversation: {name}")
    CONVERSATION_RESUMED = N_("Conversation resumed: {name}")
    CONVERSATION_REFRESHED = N_("Conversation refreshed. New messages: {count}.")
    CONVERSATION_NOT_SAVED = N_("This conversation has no history yet.")
    CONVERSATION_RENAMED = N_("Conversation renamed: {name}")
    CONVERSATION_BRANCHED = N_("New conversation branch: {name}")
    CONVERSATION_EXPORTED = N_("Conversation exported to {path}.")
    AGENT_UPDATED = N_("Agent updated.")
    CLAUDE_THINKING = N_("Claude is thinking.")
    CLAUDE_USING_TOOL = N_("Claude uses the tool {tool}.")
    CLAUDE_ANSWERING = N_("Claude is answering.")
    CLAUDE_DONE = N_("Claude has answered.")
    CLAUDE_INTERRUPTING = N_("Interrupting Claude.")
    CLAUDE_INTERRUPTED = N_("Claude was interrupted.")
    CLAUDE_FAILED = N_("Claude could not answer: {details}")
    PERMISSION_DENIED = N_("Permission denied for the tool {tool}.")
    HEADING = N_("{title}, title {level}")
    NO_NEXT_HEADING = N_("No next heading.")
    NO_PREVIOUS_HEADING = N_("No previous heading.")
    NO_NEXT_HEADING_OF_LEVEL = N_("No next title {level}.")
    NO_PREVIOUS_HEADING_OF_LEVEL = N_("No previous title {level}.")


class MessageSink(Protocol):
    """Receives the text to present to the user (through a screen reader, for instance)."""

    def show(self, text: str) -> None:
        """Present ``text``; raise ``ScreenReaderOutputError`` if it cannot be sent."""
        ...

    def close(self) -> None:
        """Release what the sink uses (when another sink replaces it)."""
        ...


class NullMessageSink:
    """The sink of the "no output" setting: the message goes nowhere."""

    def show(self, text: str) -> None:
        """Do nothing."""

    def close(self) -> None:
        """Nothing to release."""


class RecordingMessageSink:
    """Keeps the messages it receives (for tests)."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    def show(self, text: str) -> None:
        """Remember ``text``."""
        self.messages.append(text)

    def close(self) -> None:
        """Nothing to release."""


class AnnouncementCenter:
    """The single entry point for announcements.

    If the sink fails, ``on_error`` is told (the user must know) and the center falls back to
    the null sink so that the failure is reported once rather than at every announcement.
    """

    def __init__(
        self,
        message_sink: MessageSink | None = None,
        on_error: Callable[[ScreenReaderOutputError], None] | None = None,
    ) -> None:
        self.message_sink: MessageSink = message_sink or NullMessageSink()
        self._on_error = on_error

    @staticmethod
    def text(announce: Announce, **values: object) -> str:
        """The text of ``announce`` filled with ``values``, without saying it."""
        return _(announce.value).format(**values)

    def notify(self, announce: Announce, **values: object) -> str:
        """Say ``announce`` (its text filled with ``values``) and return that text."""
        text = self.text(announce, **values)
        try:
            self.message_sink.show(text)
        except ScreenReaderOutputError as error:
            self.message_sink = NullMessageSink()
            if self._on_error is not None:
                self._on_error(error)
        return text
