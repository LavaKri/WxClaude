"""Where the caret goes when the text is built again: no window."""

import pytest

from wxclaude.core.conversation.caret_anchor import CaretAnchor
from wxclaude.core.conversation.conversation_document import ConversationDocument
from wxclaude.core.conversation.messages import Message, Role

pytestmark = pytest.mark.unit


def _document(*messages: Message) -> ConversationDocument:
    document = ConversationDocument()
    document.rebuild(list(messages))
    return document


FIRST = Message("1", Role.USER, "Hello")
ANSWER = Message("2", Role.ASSISTANT, "A long answer", model="m")
SECOND = Message("3", Role.USER, "Again")


def test_the_caret_stays_at_the_same_place_in_its_message() -> None:
    document = _document(FIRST, ANSWER, SECOND)
    span = document.spans[1]
    anchor = CaretAnchor.take(document, span.start + 3)
    document.rebuild([Message("0", Role.USER, "Before it"), FIRST, ANSWER, SECOND])
    moved = next(s for s in document.spans if s.message.id == "2")
    assert anchor.position(document) == moved.start + 3


def test_a_caret_at_the_end_stays_at_the_end_when_the_text_grows() -> None:
    document = _document(FIRST, ANSWER)
    anchor = CaretAnchor.take(document, len(document.text))
    document.rebuild([FIRST, ANSWER, SECOND])
    assert anchor.position(document) == len(document.text)


def test_a_message_with_another_identifier_is_found_by_its_rank_among_its_role() -> None:
    document = _document(FIRST, ANSWER, SECOND)
    anchor = CaretAnchor.take(document, document.spans[2].start + 1)
    document.rebuild(
        [
            Message("u1", Role.USER, "Hello"),
            Message("a1", Role.ASSISTANT, "x"),
            Message("u2", Role.USER, "Again"),
        ]
    )
    assert anchor.position(document) == document.spans[2].start + 1


def test_the_offset_is_kept_inside_a_message_that_became_shorter() -> None:
    document = _document(FIRST, ANSWER)
    span = document.spans[1]
    anchor = CaretAnchor.take(document, span.end - 1)
    document.rebuild([FIRST, Message("2", Role.ASSISTANT, "Hi", model="m")])
    new = document.spans[1]
    assert new.start <= anchor.position(document) < new.end


def test_a_message_that_is_gone_sends_the_caret_to_the_start() -> None:
    document = _document(FIRST, ANSWER, SECOND)
    anchor = CaretAnchor.take(document, document.spans[1].start + 1)
    document.rebuild([FIRST])
    assert anchor.position(document) == 0


def test_an_empty_view_has_its_caret_at_the_end_and_stays_there() -> None:
    document = _document()
    anchor = CaretAnchor.take(document, 0)
    assert anchor.message is None
    document.rebuild([FIRST])
    assert anchor.position(document) == len(document.text)
