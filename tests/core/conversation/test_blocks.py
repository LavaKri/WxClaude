import pytest

from wxclaude.core.conversation.blocks import (
    Block,
    BlockKind,
    block_starts,
    next_block,
    previous_block,
    sibling_items,
)

pytestmark = pytest.mark.unit

TEXT = (
    "Intro\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n- one\n  - nested\n  - deeper\n- two\n\n"
    "1. first\n2. second\n\n```\n- code\n| x |\n|---|\n```\n"
)


def _lines(blocks: list[Block]) -> list[str]:
    return [TEXT[block.start : TEXT.index("\n", block.start)] for block in blocks]


def test_tables_lists_and_items_are_found_by_their_first_line() -> None:
    found = block_starts(TEXT)
    assert _lines(found[BlockKind.TABLE]) == ["| A | B |"]
    assert _lines(found[BlockKind.LIST]) == ["- one", "1. first"]
    assert _lines(found[BlockKind.ITEM]) == [
        "- one",
        "  - nested",
        "  - deeper",
        "- two",
        "1. first",
        "2. second",
    ]


def test_a_list_in_a_quote_is_a_list_of_level_one() -> None:
    found = block_starts("> - a\n> - b\n")
    assert len(found[BlockKind.LIST]) == 1
    assert len(found[BlockKind.ITEM]) == 2


def test_nothing_to_find() -> None:
    assert block_starts("just text\n") == {kind: [] for kind in BlockKind}


def test_a_table_knows_its_columns_and_rows_and_a_list_its_items() -> None:
    found = block_starts(TEXT)
    (table,) = found[BlockKind.TABLE]
    assert (table.columns, table.count) == (2, 1)
    assert [lst.count for lst in found[BlockKind.LIST]] == [2, 2]  # the nested items do not count


def test_a_table_without_row() -> None:
    (table,) = block_starts("| A | B | C |\n|---|---|---|\n")[BlockKind.TABLE]
    assert (table.columns, table.count) == (3, 0)


def test_next_and_previous_block() -> None:
    blocks = [Block(5), Block(20), Block(40)]
    assert next_block(blocks, 0) is blocks[0]
    assert next_block(blocks, 5) is blocks[1]
    assert next_block(blocks, 40) is None
    assert previous_block(blocks, 41) is blocks[2]
    assert previous_block(blocks, 40) is blocks[1]
    assert previous_block(blocks, 5) is None


def _sibling_lines(text_before_caret: str) -> list[str]:
    found = block_starts(TEXT)
    position = TEXT.index(text_before_caret)
    return _lines(sibling_items(found[BlockKind.ITEM], position))


def test_the_siblings_are_the_items_of_the_list_the_caret_is_in() -> None:
    assert _sibling_lines("- one") == ["- one", "- two"]  # on an item of level 1
    assert _sibling_lines("- two") == ["- one", "- two"]
    assert _sibling_lines("1. first") == ["1. first", "2. second"]  # another list


def test_in_a_nested_list_the_siblings_are_the_nested_items() -> None:
    assert _sibling_lines("  - nested") == ["  - nested", "  - deeper"]
    assert _sibling_lines("- deeper") == ["  - nested", "  - deeper"]


def test_outside_any_list_there_are_no_siblings() -> None:
    assert _sibling_lines("Intro") == []
    assert _sibling_lines("| 1 | 2 |") == []
