"""Moving through the conversation by headings, tables, lists, items and links.

Taken out of ``ConversationView``: it decides where the caret goes and what is said on arriving
(or when there is nothing further), and leaves the moving itself to the view. The screen reader
does not read the line when the application moves the caret, so every jump is announced.
"""

from collections.abc import Callable

from wxclaude.core.conversation.blocks import (
    Block,
    BlockKind,
    block_starts,
    next_block,
    previous_block,
    sibling_items,
)
from wxclaude.core.conversation.headings import (
    Heading,
    next_heading,
    parse_headings,
    previous_heading,
)
from wxclaude.core.speech.announcements import Announce
from wxclaude.i18n import ngettext

#: What is said when there is nothing further: (kind, backwards) -> announcement.
_BLOCK_MISSING = {
    (BlockKind.TABLE, False): Announce.NO_NEXT_TABLE,
    (BlockKind.TABLE, True): Announce.NO_PREVIOUS_TABLE,
    (BlockKind.LIST, False): Announce.NO_NEXT_LIST,
    (BlockKind.LIST, True): Announce.NO_PREVIOUS_LIST,
    (BlockKind.ITEM, False): Announce.NO_NEXT_ITEM,
    (BlockKind.ITEM, True): Announce.NO_PREVIOUS_ITEM,
    (BlockKind.LINK, False): Announce.NO_NEXT_LINK,
    (BlockKind.LINK, True): Announce.NO_PREVIOUS_LINK,
}


def _arrival(kind: BlockKind, block: Block, line: str) -> tuple[Announce, dict[str, str]]:
    """What is said on arriving at ``block`` (its first line is ``line``)."""
    if kind is BlockKind.TABLE:
        columns = ngettext("{count} column", "{count} columns", block.columns)
        rows = ngettext("{count} row", "{count} rows", block.count)
        return Announce.MOVED_TABLE, {
            "columns": columns.format(count=block.columns),
            "rows": rows.format(count=block.count),
            "line": line,
        }
    if kind is BlockKind.LIST:
        items = ngettext("{count} item", "{count} items", block.count)
        return Announce.MOVED_LIST, {"items": items.format(count=block.count), "line": line}
    if kind is BlockKind.LINK:
        return Announce.MOVED_LINK, {"label": block.label, "line": block.label}
    return Announce.MOVED, {"line": line}


class ConversationNavigator:
    """The jumps of the conversation. ``text`` is the text of the view, ``caret`` the Python index
    of the caret, ``move`` puts the caret at an index, ``say`` announces."""

    def __init__(
        self,
        text: Callable[[], str],
        caret: Callable[[], int],
        move: Callable[[int], None],
        say: Callable[..., None],
    ) -> None:
        self._text = text
        self._caret = caret
        self._move = move
        self._say = say

    def jump_heading(self, level: int | None, *, backwards: bool) -> None:
        """Go to the next or previous heading (of ``level``, any when None)."""
        headings = parse_headings(self._text())
        position = self._caret()
        if backwards:
            target = previous_heading(headings, position, level)
        else:
            target = next_heading(headings, position, level)
        if target is None:
            self._say(self._missing(level, backwards=backwards), level=level)
            return
        self._go_to(target)

    def jump_block(self, kind: BlockKind, *, backwards: bool) -> None:
        """Go to the next or previous table, list, item or link."""
        text = self._text()
        blocks = block_starts(text)[kind]
        position = self._caret()
        if kind is BlockKind.ITEM:
            blocks = sibling_items(blocks, position)  # the items of the list the caret is in
        target = previous_block(blocks, position) if backwards else next_block(blocks, position)
        if target is None:
            self._say(_BLOCK_MISSING[kind, backwards])
            return
        end = text.find("\n", target.start)
        line = text[target.start : end if end >= 0 else len(text)]
        self._move(target.start)
        announce, values = _arrival(kind, target, line)
        self._say(announce, **values)

    # -- inside ---------------------------------------------------------------------------

    @staticmethod
    def _missing(level: int | None, *, backwards: bool) -> Announce:
        if level is None:
            return Announce.NO_PREVIOUS_HEADING if backwards else Announce.NO_NEXT_HEADING
        if backwards:
            return Announce.NO_PREVIOUS_HEADING_OF_LEVEL
        return Announce.NO_NEXT_HEADING_OF_LEVEL

    def _go_to(self, heading: Heading) -> None:
        self._move(heading.start)
        self._say(
            Announce.MOVED_HEADING, title=heading.title, level=heading.level, line=heading.title
        )
