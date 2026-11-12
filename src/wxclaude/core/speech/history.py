"""The history of the announcements: what was said and when, so that none is lost.

It lives in memory, is shared by every conversation and keeps the last ``HISTORY_LIMIT`` entries.
A change of workspace or of conversation is an entry that starts after a blank line, which marks
where one stretch ends and the next begins.
"""

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

HISTORY_LIMIT = 500


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    """One line of the history: the time, the text, and whether a blank line comes before."""

    when: datetime
    text: str
    after_blank: bool = False


class AnnouncementHistory:
    """The last announcements, oldest first. ``clock`` gives the time of an entry (the tests
    replace it)."""

    def __init__(
        self, limit: int = HISTORY_LIMIT, clock: Callable[[], datetime] = datetime.now
    ) -> None:
        self._entries: deque[HistoryEntry] = deque(maxlen=limit)
        self._clock = clock

    def add(self, text: str) -> None:
        """Record ``text`` (on one line: the breaks of a long message become spaces)."""
        self._entries.append(HistoryEntry(self._clock(), " ".join(text.split())))

    def add_change(self, text: str) -> None:
        """Record a change of workspace or of conversation, after a blank line."""
        self._entries.append(HistoryEntry(self._clock(), " ".join(text.split()), after_blank=True))

    def lines(self) -> list[str]:
        """The history as text lines: ``14:32 Claude has answered.``; a change follows a blank
        line (none at the very start)."""
        lines: list[str] = []
        for entry in self._entries:
            if entry.after_blank and lines:
                lines.append("")
            lines.append(f"{entry.when:%H:%M} {entry.text}")
        return lines

    def __len__(self) -> int:
        return len(self._entries)
