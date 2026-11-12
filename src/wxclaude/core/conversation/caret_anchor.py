"""Where the caret goes when the text of the conversation is built again.

The caret stays on its message, at the same place in it (or at the end when it was at the end).
``take`` notes where it is before the text is rebuilt, ``position`` finds the place in the new text.
"""

from dataclasses import dataclass

from wxclaude.core.conversation.conversation_document import ConversationDocument, MessageSpan
from wxclaude.core.conversation.messages import Message


@dataclass(frozen=True, slots=True)
class CaretAnchor:
    """The caret in terms that survive a rebuild: the message it was in, the rank of that message
    among those of its role, and how far in it the caret was. ``message`` is None when the caret
    was in no message (an empty view, for example)."""

    at_end: bool
    message: Message | None = None
    rank: int = -1
    offset: int = 0

    @classmethod
    def take(cls, document: ConversationDocument, caret: int) -> CaretAnchor:
        """Note where ``caret`` (a Python index of the text of ``document``) is."""
        at_end = caret >= len(document.text)
        span = document.span_at(caret)
        if span is None:
            return cls(at_end)
        rank = sum(
            1
            for other in document.spans
            if other.message.role is span.message.role and other.start < span.start
        )
        return cls(at_end, span.message, rank, caret - span.start)

    def position(self, document: ConversationDocument) -> int:
        """The index of the caret in the rebuilt ``document``: the end when it was at the end, the
        same place in the same message, else the start."""
        if self.at_end:
            return len(document.text)
        span = self._same_message(document)
        if span is None:
            return 0
        return span.start + min(self.offset, max(0, span.end - span.start - 1))

    def _same_message(self, document: ConversationDocument) -> MessageSpan | None:
        """The message of the rebuilt text that the caret was in. Messages shown live have
        identifiers of their own and those read from the session file have the CLI's: when the
        identifier is gone, it is the message with the same rank among those of its role."""
        if self.message is None:
            return None
        spans = document.spans
        found = next((s for s in spans if s.message.id == self.message.id), None)
        if found is not None:
            return found
        same_role = [s for s in spans if s.message.role is self.message.role]
        return same_role[self.rank] if 0 <= self.rank < len(same_role) else None
