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
    NEW_CONVERSATION = N_("New conversation.")
    CONVERSATION_EXPORTED = N_("Conversation exported to {path}.")
    AGENT_UPDATED = N_("Agent updated.")


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

    def notify(self, announce: Announce, **values: object) -> str:
        """Say ``announce`` (its text filled with ``values``) and return that text."""
        text = _(announce.value).format(**values)
        try:
            self.message_sink.show(text)
        except ScreenReaderOutputError as error:
            self.message_sink = NullMessageSink()
            if self._on_error is not None:
                self._on_error(error)
        return text
