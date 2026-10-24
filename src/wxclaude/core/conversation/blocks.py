"""Tables, lists and list items of a Markdown document, and navigation between them.

Like the headings (``headings.py``), they are found in the text the field shows, so the offsets are
Python string indexes of that text. The lists that are not inside another list count (``L``); the
items of every list are kept, each knowing its list, so that ``I`` stays among the items of the
list the caret is in. Code blocks are ignored.
"""

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from enum import StrEnum

from markdown_it import MarkdownIt

_PARSER = MarkdownIt("commonmark").enable("table")
_LIST_OPEN = ("bullet_list_open", "ordered_list_open")
_LIST_CLOSE = ("bullet_list_close", "ordered_list_close")


class BlockKind(StrEnum):
    """What the keys of the conversation view jump between, besides the headings."""

    TABLE = "table"
    LIST = "list"
    ITEM = "item"


@dataclass(slots=True)
class Block:
    """A table, a list or an item: where it starts, and what it holds.

    ``columns`` and ``count`` are filled for a table (columns, rows without the header row) and
    ``count`` for a list (its direct items); both are 0 for an item. An item also has its ``end``
    (the offset after its last line, nested lists included) and its ``group``, the start of the list
    it belongs to; they are -1 for the others.
    """

    start: int
    columns: int = 0
    count: int = 0
    end: int = -1
    group: int = -1


def block_starts(text: str) -> dict[BlockKind, list[Block]]:
    """The tables, the lists of level 1 and the items of those lists, each in document order.

    ``text`` must use ``\n`` as line break.
    """
    line_starts = [0]
    line_starts.extend(index + 1 for index, char in enumerate(text) if char == "\n")
    found: dict[BlockKind, list[Block]] = {kind: [] for kind in BlockKind}
    lists: list[Block] = []  # the lists we are inside, the innermost last
    group_starts: list[int] = []
    table: Block | None = None
    in_body = False
    for token in _PARSER.parse(text):
        first_line = token.map[0] if token.map is not None else None
        start = line_starts[first_line] if first_line is not None else None
        if token.type == "table_open" and start is not None:
            table = Block(start)
            found[BlockKind.TABLE].append(table)
            in_body = False
        elif table is not None and token.type == "th_open":
            table.columns += 1
        elif table is not None and token.type == "tbody_open":
            in_body = True
        elif table is not None and in_body and token.type == "tr_open":
            table.count += 1
        elif token.type in _LIST_OPEN and start is not None:
            group = Block(start)
            if not lists:
                found[BlockKind.LIST].append(group)
            lists.append(group)
            group_starts.append(start)
        elif token.type in _LIST_CLOSE and lists:
            lists.pop()
            group_starts.pop()
        elif token.type == "list_item_open" and start is not None and lists and token.map:
            after = token.map[1]
            end = line_starts[after] if after < len(line_starts) else len(text)
            found[BlockKind.ITEM].append(Block(start, end=end, group=group_starts[-1]))
            lists[-1].count += 1
    return found


def next_block(blocks: list[Block], position: int) -> Block | None:
    """The first of ``blocks`` (in document order) that starts after ``position``."""
    index = bisect_right([block.start for block in blocks], position)
    return blocks[index] if index < len(blocks) else None


def previous_block(blocks: list[Block], position: int) -> Block | None:
    """The last of ``blocks`` (in document order) that starts before ``position``."""
    index = bisect_left([block.start for block in blocks], position)
    return blocks[index - 1] if index > 0 else None


def sibling_items(items: list[Block], position: int) -> list[Block]:
    """The items of the list that holds the item the caret is in (``position``), nested or not.

    The item is the innermost one whose lines contain ``position``; none when the caret is not in
    a list.
    """
    inside = [item for item in items if item.start <= position < item.end]
    if not inside:
        return []
    group = max(inside, key=lambda item: item.start).group
    return [item for item in items if item.group == group]
