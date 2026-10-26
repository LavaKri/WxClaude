"""Announcements: what the application says about what it just did, and where it goes.

Every message is a member of ``Announce``. Most belong to a ``Category``: the user chooses a
``Destination`` per category (Preferences > Announcements), among the ones the category accepts,
not per message. The others are fixed: they are always said as a message. The code only calls
``AnnouncementCenter.notify``; how a message really reaches the user is the business of the sink
and of the sound player the center is connected to (see ``ui/message_sinks.py``,
``core/sounds.py``).
"""

import enum
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from wxclaude.core.errors import ScreenReaderOutputError
from wxclaude.i18n import N_, _


class Destination(enum.Enum):
    """What is done with the announcements of a category."""

    NONE = "none"
    MESSAGE = "message"  # the text of the announcement
    READ_LINE = "read_line"  # the text of the line concerned, given as ``line``
    DIALOG = "dialog"  # the text in a message box the user closes
    SOUND_1 = "sound_1"  # the end of an answer
    SOUND_2 = "sound_2"  # a question of permission

    @property
    def label(self) -> str:
        """Message id of the name shown in the Preferences (translate with ``_``)."""
        return _DESTINATION_LABELS[self]

    @property
    def is_sound(self) -> bool:
        """Is the announcement a sound instead of a text?"""
        return self in (Destination.SOUND_1, Destination.SOUND_2)


_DESTINATION_LABELS = {
    Destination.NONE: N_("No announcement"),
    Destination.MESSAGE: N_("Message"),
    Destination.READ_LINE: N_("Read the line"),
    Destination.DIALOG: N_("Dialog box"),
    # The names of the files, as they are (not translated).
    Destination.SOUND_1: "Message.wav",
    Destination.SOUND_2: "Permission.wav",
}


@dataclass(frozen=True, slots=True)
class Category:
    """A group of announcements that share one destination; ``label`` is a message id.

    ``choices`` are the destinations the user may pick (the first one is "nothing" by convention);
    ``default`` is one of them. A message of a category with ``in_status_bar`` False is only said,
    not written in the status bar.
    """

    id: str
    label: str
    default: Destination
    choices: tuple[Destination, ...]
    in_status_bar: bool = True

    def accepts(self, destination: Destination) -> bool:
        """Can the announcements of this category go to ``destination``?"""
        return destination in self.choices


_NONE_OR_MESSAGE = (Destination.NONE, Destination.MESSAGE)

#: What Claude is doing while it answers.
PROGRESS = Category("progress", N_("Progress of Claude"), Destination.MESSAGE, _NONE_OR_MESSAGE)
#: Claude starts a step of its task list.
STEP = Category(
    "step", N_("Step in progress"), Destination.MESSAGE, _NONE_OR_MESSAGE, in_status_bar=False
)
#: An answer is over (or was interrupted).
END_OF_ANSWER = Category(
    "end_of_answer",
    N_("End of an answer"),
    Destination.SOUND_1,
    (Destination.NONE, Destination.MESSAGE, Destination.SOUND_1),
    in_status_bar=False,  # "Ready" takes its place there
)
#: Claude asks a question of permission (the dialog opens).
PERMISSION_QUESTION = Category(
    "permission_question",
    N_("Question of permission"),
    Destination.SOUND_2,
    (Destination.NONE, Destination.MESSAGE, Destination.SOUND_2),
    in_status_bar=False,
)
#: The way a question of permission ended.
PERMISSION_ANSWER = Category(
    "permission_answer", N_("Answer to a permission"), Destination.MESSAGE, _NONE_OR_MESSAGE
)
#: A jump in the conversation (heading, table, list, item) that arrived.
MOVEMENT = Category(
    "movement",
    N_("Conversation, movement done"),
    Destination.MESSAGE,
    (Destination.NONE, Destination.MESSAGE, Destination.READ_LINE),
    in_status_bar=False,
)
#: A jump that reached nothing (no more heading, table, list or item in that direction).
MOVEMENT_BLOCKED = Category(
    "movement_blocked",
    N_("Conversation, no further movement possible"),
    Destination.MESSAGE,
    _NONE_OR_MESSAGE,
    in_status_bar=False,
)
#: A search that selected an occurrence.
SEARCH = Category(
    "search", N_("Search reached"), Destination.MESSAGE, _NONE_OR_MESSAGE, in_status_bar=False
)
#: A search that found no more occurrence in the direction asked.
SEARCH_FAILED = Category(
    "search_failed",
    N_("Unsuccessful search"),
    Destination.MESSAGE,
    (Destination.NONE, Destination.MESSAGE, Destination.DIALOG),
    in_status_bar=False,
)
#: A gauge of the subscription (the 5 hours, the week) reached its alert threshold.
GAUGE = Category(
    "gauge", N_("Gauge alerts"), Destination.MESSAGE, _NONE_OR_MESSAGE, in_status_bar=False
)  # the "Ready" line of the status bar shows the gauges worth a look (``UsageTracker.ready_line``)
#: The conversation read again.
REFRESH = Category("refresh", N_("Refresh"), Destination.MESSAGE, _NONE_OR_MESSAGE)

#: Every category, in the order of the Announcements page of the Preferences.
CATEGORIES = (
    PROGRESS,
    STEP,
    END_OF_ANSWER,
    PERMISSION_QUESTION,
    PERMISSION_ANSWER,
    MOVEMENT,
    MOVEMENT_BLOCKED,
    SEARCH,
    SEARCH_FAILED,
    REFRESH,
    GAUGE,
)


class Announce(enum.Enum):
    """All the messages of the application: a category (None: always said as a message) and
    ``text``, a message id (translate, then format)."""

    NO_CONVERSATION = (None, N_("No conversation in this workspace."))
    CLAUDE_FAILED = (None, N_("Claude could not answer: {details}"))
    CONVERSATION_REFRESHED = (REFRESH, N_("Conversation refreshed. New messages: {count}."))
    CONVERSATION_NOT_SAVED = (REFRESH, N_("This conversation has no history yet."))
    CONVERSATION_DELETED = (None, N_('Conversation "{name}" moved to the Recycle Bin.'))
    SEARCH_FOUND = (SEARCH, N_("{line}"))
    SEARCH_NO_NEXT = (SEARCH_FAILED, N_('No next occurrence of "{term}".'))
    SEARCH_NO_PREVIOUS = (SEARCH_FAILED, N_('No previous occurrence of "{term}".'))
    CLAUDE_THINKING = (PROGRESS, N_("Claude is thinking."))
    CLAUDE_USING_TOOL = (PROGRESS, N_("Claude uses the tool {tool}."))
    CLAUDE_ANSWERING = (PROGRESS, N_("Claude is answering."))
    CLAUDE_INTERRUPTING = (PROGRESS, N_("Interrupting Claude."))
    PERMISSION_DENIED = (PROGRESS, N_("Permission denied for the tool {tool}."))
    GAUGE_FIVE_HOUR = (GAUGE, N_("Alert: the 5-hour gauge is at {percent} %."))
    GAUGE_WEEKLY = (GAUGE, N_("Alert: the weekly gauge is at {percent} %."))
    STEP_STARTED = (STEP, N_("Step {number} of {total}: {subject}"))
    CLAUDE_DONE = (END_OF_ANSWER, N_("Claude has answered."))
    CLAUDE_INTERRUPTED = (END_OF_ANSWER, N_("Claude was interrupted."))
    PERMISSION_ASKED = (PERMISSION_QUESTION, N_("Claude asks permission for the tool {tool}."))
    PLAN_PROPOSED = (PERMISSION_QUESTION, N_("Claude proposes a plan."))
    QUESTION_ASKED = (PERMISSION_QUESTION, N_("Claude has questions for you."))
    QUESTION_ANSWERED = (PERMISSION_ANSWER, N_("Your answers were sent to Claude."))
    PERMISSION_GRANTED = (PERMISSION_ANSWER, N_("Permission granted for the tool {tool}."))
    PERMISSION_REFUSED = (PERMISSION_ANSWER, N_("Permission refused for the tool {tool}."))
    PLAN_REFUSED = (
        PERMISSION_ANSWER,
        N_("Claude asked to leave the Plan mode: refused, as set in the Preferences."),
    )
    PERMISSION_EXPIRED = (
        PERMISSION_ANSWER,
        N_("The question about the tool {tool} expired: Claude denied the tool."),
    )
    MOVED = (MOVEMENT, N_("{line}"))
    MOVED_HEADING = (MOVEMENT, N_("{title}, title {level}"))
    MOVED_TABLE = (MOVEMENT, N_("Table of {columns} and {rows}. {line}"))
    MOVED_LIST = (MOVEMENT, N_("List of {items}. {line}"))
    MOVED_LINK = (MOVEMENT, N_("Link: {label}"))
    NO_NEXT_HEADING = (MOVEMENT_BLOCKED, N_("No next heading."))
    NO_PREVIOUS_HEADING = (MOVEMENT_BLOCKED, N_("No previous heading."))
    NO_NEXT_HEADING_OF_LEVEL = (MOVEMENT_BLOCKED, N_("No next title {level}."))
    NO_PREVIOUS_HEADING_OF_LEVEL = (MOVEMENT_BLOCKED, N_("No previous title {level}."))
    NO_NEXT_TABLE = (MOVEMENT_BLOCKED, N_("No next table."))
    NO_PREVIOUS_TABLE = (MOVEMENT_BLOCKED, N_("No previous table."))
    NO_NEXT_LIST = (MOVEMENT_BLOCKED, N_("No next list."))
    NO_PREVIOUS_LIST = (MOVEMENT_BLOCKED, N_("No previous list."))
    NO_NEXT_ITEM = (MOVEMENT_BLOCKED, N_("No next list item."))
    NO_NEXT_LINK = (MOVEMENT_BLOCKED, N_("No next link."))
    NO_PREVIOUS_LINK = (MOVEMENT_BLOCKED, N_("No previous link."))
    NO_PREVIOUS_ITEM = (MOVEMENT_BLOCKED, N_("No previous list item."))

    def __init__(self, category: Category | None, text: str) -> None:
        self.category = category
        self.text = text


class MessageSink(Protocol):
    """Receives the text to present to the user (through a screen reader, for instance)."""

    def show(self, text: str) -> None:
        """Present ``text``; raise ``ScreenReaderOutputError`` if it cannot be sent."""
        ...

    def close(self) -> None:
        """Release what the sink uses (when another sink replaces it)."""
        ...


class SoundPlayer(Protocol):
    """Plays the sound of a destination (``SOUND_1`` or ``SOUND_2``) without waiting for its end."""

    def play(self, destination: Destination) -> None:
        """Start the sound; raise ``ScreenReaderOutputError`` if it cannot be played."""
        ...


class NullMessageSink:
    """The sink of the "no output" setting: the message goes nowhere."""

    def show(self, text: str) -> None:
        """Do nothing."""

    def close(self) -> None:
        """Nothing to release."""


class NullSoundPlayer:
    """Plays nothing."""

    def play(self, destination: Destination) -> None:
        """Do nothing."""


class RecordingMessageSink:
    """Keeps the messages it receives (for tests)."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    def show(self, text: str) -> None:
        """Remember ``text``."""
        self.messages.append(text)

    def close(self) -> None:
        """Nothing to release."""


class RecordingSoundPlayer:
    """Keeps the sounds it is asked to play (for tests)."""

    def __init__(self) -> None:
        self.played: list[Destination] = []

    def play(self, destination: Destination) -> None:
        """Remember ``destination``."""
        self.played.append(destination)


class AnnouncementCenter:
    """The single entry point for announcements.

    ``show_dialog`` shows a text in a message box (the ``DIALOG`` destination).
    If the sink or the sound player fails, ``on_error`` is told (the user must know) and the center
    falls back to the null one so that the failure is reported once rather than at every
    announcement.
    """

    def __init__(
        self,
        message_sink: MessageSink | None = None,
        destination_of: Callable[[Category], Destination] | None = None,
        on_error: Callable[[ScreenReaderOutputError], None] | None = None,
        sound_player: SoundPlayer | None = None,
        show_dialog: Callable[[str], None] | None = None,
    ) -> None:
        self.message_sink: MessageSink = message_sink or NullMessageSink()
        self.sound_player: SoundPlayer = sound_player or NullSoundPlayer()
        self._destination_of = destination_of or (lambda category: category.default)
        self._on_error = on_error
        self._show_dialog = show_dialog

    @staticmethod
    def text(announce: Announce, **values: object) -> str:
        """The text of ``announce`` filled with ``values``, without saying it."""
        return _(announce.text).format(**values)

    def destination(self, announce: Announce) -> Destination:
        """Where ``announce`` goes now (a fixed announcement is always a message)."""
        category = announce.category
        if category is None:
            return Destination.MESSAGE
        destination = self._destination_of(category)
        return destination if category.accepts(destination) else category.default

    def notify(self, announce: Announce, **values: object) -> str | None:
        """Say ``announce`` (its text filled with ``values``) where its destination says.

        ``values`` may carry ``line``, the text of the line concerned (what ``READ_LINE`` sends).
        Returns the text to write in the status bar: the text that was sent, None if the
        announcement is a sound, a dialog, nothing, or of a category kept out of the status bar.
        """
        destination = self.destination(announce)
        if destination is Destination.NONE:
            return None
        if destination.is_sound:
            self._play(destination)
            return None
        text = self.text(announce, **values)
        if destination is Destination.DIALOG:
            if self._show_dialog is not None:
                self._show_dialog(text)
            return None
        if destination is Destination.READ_LINE:
            text = str(values.get("line", text))
        try:
            self.message_sink.show(text)
        except ScreenReaderOutputError as error:
            self.message_sink = NullMessageSink()
            self._report(error)
        category = announce.category
        return text if category is None or category.in_status_bar else None

    def _play(self, destination: Destination) -> None:
        try:
            self.sound_player.play(destination)
        except ScreenReaderOutputError as error:
            self.sound_player = NullSoundPlayer()
            self._report(error)

    def _report(self, error: ScreenReaderOutputError) -> None:
        if self._on_error is not None:
            self._on_error(error)
