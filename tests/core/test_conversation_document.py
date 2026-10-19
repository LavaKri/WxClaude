import pytest

from wxclaude.core.conversation_document import ConversationDocument, message_title, preview
from wxclaude.core.headings import parse_headings
from wxclaude.core.messages import Message, Role

pytestmark = pytest.mark.unit


def _prompt(text: str, hidden: bool = False) -> Message:
    return Message("u", Role.USER, text, hidden=hidden)


def _answer(text: str, model: str | None = "m", effort: str | None = None) -> Message:
    return Message("a", Role.ASSISTANT, text, model=model, effort=effort)


def test_preview_keeps_a_short_first_sentence() -> None:
    assert preview("Hello there. And more.") == "Hello there."


def test_preview_cuts_a_long_sentence_at_twenty_words() -> None:
    long_text = " ".join(f"w{n}" for n in range(30))
    assert preview(long_text) == " ".join(f"w{n}" for n in range(20)) + "…"


def test_preview_is_one_line() -> None:
    assert preview("first\nline\n\nsecond") == "first line second"


def test_titles() -> None:
    assert message_title(_prompt("Hi")) == "You say: Hi"
    assert message_title(_answer("x", model=None)) == "Claude answered"
    assert message_title(_answer("x")) == "Answer from m"
    assert message_title(_answer("x", effort="xhigh")) == "Answer from m, effort very high"


def test_prompts_are_level_one_and_answers_level_two_headings() -> None:
    document = ConversationDocument()
    document.append(_prompt("Hi"))
    document.append(_answer("# Inside\ntext"))
    headings = parse_headings(document.text)
    assert [(h.level, h.title) for h in headings] == [
        (1, "You say: Hi"),
        (2, "Answer from m"),
        (1, "Inside"),
    ]


def test_append_returns_only_the_added_text() -> None:
    document = ConversationDocument()
    first = document.append(_prompt("Hi"))
    second = document.append(_answer("Yo"))
    assert document.text == first + second
    assert second == "## Answer from m\nYo\n\n"


def test_hidden_messages_are_skipped_unless_asked() -> None:
    hidden = _prompt("continue", hidden=True)
    document = ConversationDocument()
    assert document.append(hidden) == ""
    assert document.spans == []
    shown = ConversationDocument(show_hidden=True)
    assert shown.append(hidden) != ""


def test_span_at_finds_the_message_under_the_caret() -> None:
    document = ConversationDocument()
    prompt, answer = _prompt("Hi"), _answer("Yo")
    document.append(prompt)
    document.append(answer)
    first, second = document.spans
    assert document.span_at(0) is first
    assert document.span_at(first.end - 1) is first
    assert document.span_at(second.start) is second
    assert document.span_at(len(document.text)) is second
    assert ConversationDocument().span_at(0) is None


def test_rebuild_replaces_everything() -> None:
    document = ConversationDocument()
    document.append(_prompt("old"))
    text = document.rebuild([_answer("new")])
    assert text == document.text == "## Answer from m\nnew\n\n"
    assert len(document.spans) == 1
