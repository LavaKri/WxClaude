"""The conversation as one Markdown document.

The text field only shows a projection of the list of messages. Each message remembers where it
lies in the text (a span), so the message under the caret can be found back (context menu, copy).
Messages are only ever appended, so the field is never rewritten in the middle.
"""

import re
from bisect import bisect_right
from dataclasses import dataclass

from wxclaude.core.messages import Message, Role
from wxclaude.i18n import N_, _

PREVIEW_WORDS = 20

_EFFORT_NAMES = {
    "low": N_("low"),
    "medium": N_("medium"),
    "high": N_("high"),
    "xhigh": N_("very high"),
    "max": N_("maximum"),
}
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


@dataclass(frozen=True, slots=True)
class MessageSpan:
    """Where a message lies in the document (``end`` excluded, the blank line included)."""

    message: Message
    start: int
    end: int


def preview(text: str) -> str:
    """The first sentence of ``text`` if it has 20 words or fewer, else 20 words and ``…``."""
    collapsed = " ".join(text.split())
    sentence = _SENTENCE_END.split(collapsed, maxsplit=1)[0]
    words = sentence.split()
    if len(words) <= PREVIEW_WORDS:
        return sentence
    return " ".join(words[:PREVIEW_WORDS]) + "…"


def message_title(message: Message) -> str:
    """The level 1 title that introduces ``message`` (without the ``#``)."""
    if message.role is Role.USER:
        return _("You say: {preview}").format(preview=preview(message.text))
    if message.model is None:
        return _("Claude answered")
    if message.effort is None:
        return _("Answer from {model}").format(model=message.model)
    effort = _(_EFFORT_NAMES.get(message.effort, message.effort))
    return _("Answer from {model}, effort {effort}").format(model=message.model, effort=effort)


def title_level(message: Message) -> int:
    """The heading level of the title of ``message``: 1 for a prompt, 2 for an answer."""
    return 1 if message.role is Role.USER else 2


def render_message(message: Message) -> str:
    """The text a message adds to the document: its title, its text and a blank line."""
    hashes = "#" * title_level(message)
    return f"{hashes} {message_title(message)}\n{message.text}\n\n"


class ConversationDocument:
    """The messages shown, the text they make, and the span of each in that text."""

    def __init__(self, *, show_hidden: bool = False) -> None:
        self.show_hidden = show_hidden
        self._text = ""
        self._spans: list[MessageSpan] = []
        self._starts: list[int] = []

    @property
    def text(self) -> str:
        return self._text

    @property
    def spans(self) -> list[MessageSpan]:
        return list(self._spans)

    def clear(self) -> None:
        self._text = ""
        self._spans = []
        self._starts = []

    def append(self, message: Message) -> str:
        """Add ``message``; return the text to append to the field ('' if it is not shown)."""
        if message.hidden and not self.show_hidden:
            return ""
        added = render_message(message)
        start = len(self._text)
        self._text += added
        self._spans.append(MessageSpan(message, start, len(self._text)))
        self._starts.append(start)
        return added

    def rebuild(self, messages: list[Message]) -> str:
        """Start again from ``messages``; return the whole text."""
        self.clear()
        for message in messages:
            self.append(message)
        return self._text

    def span_at(self, position: int) -> MessageSpan | None:
        """The span of the message that holds the character index ``position``."""
        index = bisect_right(self._starts, position) - 1
        if index < 0:
            return None
        span = self._spans[index]
        return span if position < span.end or position == len(self._text) else None
