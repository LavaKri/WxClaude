import pytest

from wxclaude.core.conversation.conversations import (
    branch_name,
    default_name,
    is_conversation_id,
    new_conversation_id,
)

pytestmark = pytest.mark.unit


def test_new_identifiers_are_valid_and_different() -> None:
    first, second = new_conversation_id(), new_conversation_id()
    assert first != second
    assert is_conversation_id(first)


@pytest.mark.parametrize("text", ["", "not an id", 42, None, "1234"])
def test_other_texts_are_not_identifiers(text: object) -> None:
    assert not is_conversation_id(text)


def test_default_name_carries_the_number() -> None:
    assert default_name(3) == "Conversation 3"


def test_branch_name_follows_the_name_of_its_parent() -> None:
    assert branch_name("Conversation 3", 2) == "Conversation 3 branch 2"
