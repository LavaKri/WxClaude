"""The jumps of the conversation, with a fake caret: no window."""

import pytest

from wxclaude.core.conversation.blocks import BlockKind
from wxclaude.core.speech.announcements import Announce
from wxclaude.presenters.conversation_navigator import ConversationNavigator

pytestmark = pytest.mark.unit

TEXT = "intro\n## One\nbody\n## Two\nend\n"


class Caret:
    """A caret that moves where the navigator says, and what is said."""

    def __init__(self, text: str, index: int = 0) -> None:
        self.index = index
        self.said: list[tuple[Announce, dict[str, object]]] = []
        self.navigator = ConversationNavigator(
            lambda: text, lambda: self.index, self.move, self.say
        )

    def move(self, index: int) -> None:
        self.index = index

    def say(self, announce: Announce, **values: object) -> None:
        self.said.append((announce, values))


def test_a_heading_jump_moves_the_caret_and_says_where_it_arrived() -> None:
    caret = Caret(TEXT)
    caret.navigator.jump_heading(None, backwards=False)
    assert caret.index == TEXT.index("## One")
    announce, values = caret.said[-1]
    assert announce is Announce.MOVED_HEADING
    assert values["title"] == "One"
    caret.navigator.jump_heading(2, backwards=False)
    assert caret.index == TEXT.index("## Two")


def test_going_back_from_the_first_heading_says_there_is_none() -> None:
    caret = Caret(TEXT, TEXT.index("## One"))
    caret.navigator.jump_heading(None, backwards=True)
    assert caret.index == TEXT.index("## One")
    assert caret.said[-1][0] is Announce.NO_PREVIOUS_HEADING


def test_no_heading_of_that_level_says_so_with_the_level() -> None:
    caret = Caret(TEXT)
    caret.navigator.jump_heading(4, backwards=False)
    assert caret.said == [(Announce.NO_NEXT_HEADING_OF_LEVEL, {"level": 4})]


def test_no_table_says_there_is_none_and_the_caret_stays() -> None:
    caret = Caret(TEXT, 3)
    caret.navigator.jump_block(BlockKind.TABLE, backwards=False)
    assert caret.index == 3
    assert caret.said == [(Announce.NO_NEXT_TABLE, {})]
    caret.navigator.jump_block(BlockKind.LINK, backwards=True)
    assert caret.said[-1] == (Announce.NO_PREVIOUS_LINK, {})


def test_a_list_is_announced_with_its_items_and_first_line() -> None:
    text = "intro\n\n- a\n- b\n"
    caret = Caret(text)
    caret.navigator.jump_block(BlockKind.LIST, backwards=False)
    assert caret.index == text.index("- a")
    announce, values = caret.said[-1]
    assert announce is Announce.MOVED_LIST
    assert values["line"] == "- a"
    assert "2" in str(values["items"])
