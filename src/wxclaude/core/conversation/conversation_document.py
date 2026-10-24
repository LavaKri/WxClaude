"""The conversation as one Markdown document.

The text field only shows a projection of the list of messages. Each message remembers where it
lies in the text (a span), so the message under the caret can be found back (context menu, copy).
Messages are only ever appended, so the field is never rewritten in the middle.
"""

import re
from bisect import bisect_right
from dataclasses import dataclass

from wxclaude.core.conversation.emphasis import remove_emphasis
from wxclaude.core.conversation.messages import Message, Role
from wxclaude.core.conversation.tool_summary import summarize_tools
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


def message_title(message: Message, *, without_marks: bool = False) -> str:
    """The level 1 title that introduces ``message`` (without the ``#``)."""
    if message.role is Role.USER:
        text = remove_emphasis(message.text) if without_marks else message.text
        return _("You say: {preview}").format(preview=preview(text))
    if message.model is None:
        return _("Claude answered")
    if message.effort is None:
        return _("Answer from {model}").format(model=message.model)
    effort = _(_EFFORT_NAMES.get(message.effort, message.effort))
    return _("Answer from {model}, effort {effort}").format(model=message.model, effort=effort)


def title_level(message: Message) -> int:
    """The heading level of the title of ``message``: 1 for a prompt, 2 for an answer."""
    return 1 if message.role is Role.USER else 2


def message_header(message: Message, *, without_marks: bool = False) -> str:
    """The title line of ``message`` as written in the document, with its line break."""
    title = message_title(message, without_marks=without_marks)
    return f"{'#' * title_level(message)} {title}\n"


def render_message(
    message: Message, *, tools_summary: bool = False, without_marks: bool = False
) -> str:
    """The text a message adds to the document: its title, its text and a blank line.

    With ``tools_summary`` an answer that used tools has the line that sums them up under its text
    (it belongs to the document only: it is not part of the text of the message). With
    ``without_marks`` the marks of bold and italic are removed from the title and the text (the
    lines stay the same).
    """
    summary = summarize_tools(message.tools) if tools_summary and message.model else ""
    under = f"{summary}\n\n" if summary else ""
    text = remove_emphasis(message.text) if without_marks else message.text
    return f"{message_header(message, without_marks=without_marks)}{text}\n\n{under}"


class ConversationDocument:
    """The messages shown, the text they make, and the span of each in that text."""

    def __init__(
        self,
        *,
        show_hidden: bool = False,
        tools_summary: bool = False,
        without_marks: bool = False,
    ) -> None:
        self.show_hidden = show_hidden
        self.tools_summary = tools_summary  # a line under each answer that used tools
        self.without_marks = without_marks  # no marks of bold and italic in the text
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
        added = render_message(
            message, tools_summary=self.tools_summary, without_marks=self.without_marks
        )
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

    def prompt_position(self, position: int) -> tuple[int, int]:
        """Where ``position`` is among the prompts of the user: (its number, how many there are).

        Only the prompts shown are counted; an answer belongs to the prompt it follows. The number
        is 0 before the first prompt.
        """
        starts = [span.start for span in self._spans if span.message.role is Role.USER]
        return bisect_right(starts, position), len(starts)

    def exchange_of(self, message_id: str) -> str:
        """The text of the exchange that holds the message: the prompt of the user and every
        answer that follows it, as displayed (titles included). Answers shown before any prompt
        make an exchange without one. '' if the message is not shown. The lines that sum up
        the tools are not part of it."""
        index = next((i for i, s in enumerate(self._spans) if s.message.id == message_id), None)
        if index is None:
            return ""
        first = index
        while first > 0 and self._spans[first].message.role is not Role.USER:
            first -= 1
        last = index + 1
        while last < len(self._spans) and self._spans[last].message.role is not Role.USER:
            last += 1
        shown = (
            render_message(span.message, without_marks=self.without_marks)
            for span in self._spans[first:last]
        )
        return "".join(shown).rstrip("\n")

    def body_line(self, span: MessageSpan, position: int) -> int:
        """The line of the text of the message that holds ``position``; -1 on its title."""
        header = message_header(span.message, without_marks=self.without_marks)
        body_start = span.start + len(header)
        if position < body_start:
            return -1
        return self._text.count("\n", body_start, position)

    def span_at(self, position: int) -> MessageSpan | None:
        """The span of the message that holds the character index ``position``."""
        index = bisect_right(self._starts, position) - 1
        if index < 0:
            return None
        span = self._spans[index]
        return span if position < span.end or position == len(self._text) else None
