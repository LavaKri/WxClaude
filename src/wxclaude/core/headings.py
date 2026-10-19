"""Headings of a Markdown document, and navigation between them.

The conversation is shown as raw Markdown, so the offsets found here are offsets in the text field,
once converted to UTF-16 units (Windows text fields count a character outside the basic plane as
two units). Offsets in this module are Python string indexes unless the name says ``utf16``.
"""

from bisect import bisect_left, bisect_right
from dataclasses import dataclass

from markdown_it import MarkdownIt

_PARSER = MarkdownIt("commonmark")


@dataclass(frozen=True, slots=True)
class Heading:
    """A heading: its level (1 to 6), its text without the ``#``, and where it lies.

    ``start`` is the first character of the heading, ``end`` the end of its last line, and
    ``body_end`` the start of the next heading of any level (or the end of the text).
    """

    level: int
    title: str
    start: int
    end: int
    body_end: int


def _line_starts(text: str) -> list[int]:
    starts = [0]
    starts.extend(index + 1 for index, char in enumerate(text) if char == "\n")
    return starts


def parse_headings(text: str) -> list[Heading]:
    """The headings of ``text`` (ATX and Setext; code blocks are ignored), in document order.

    ``text`` must use ``\\n`` as line break.
    """
    starts = _line_starts(text)
    tokens = _PARSER.parse(text)
    found: list[tuple[int, int, int, str]] = []  # level, start, end, title
    for index, token in enumerate(tokens):
        if token.type != "heading_open" or token.map is None:
            continue
        first_line, after_last_line = token.map
        start = starts[first_line]
        end = starts[after_last_line] - 1 if after_last_line < len(starts) else len(text)
        inline = tokens[index + 1]
        found.append((int(token.tag[1:]), start, max(start, end), inline.content.strip()))
    headings: list[Heading] = []
    for position, (level, start, end, title) in enumerate(found):
        body_end = found[position + 1][1] if position + 1 < len(found) else len(text)
        headings.append(Heading(level, title, start, end, body_end))
    return headings


def next_heading(
    headings: list[Heading], position: int, level: int | None = None
) -> Heading | None:
    """The first heading (of ``level`` if given) that starts after ``position``."""
    starts = [heading.start for heading in headings]
    for heading in headings[bisect_right(starts, position) :]:
        if level is None or heading.level == level:
            return heading
    return None


def previous_heading(
    headings: list[Heading], position: int, level: int | None = None
) -> Heading | None:
    """The last heading (of ``level`` if given) that starts before ``position``."""
    starts = [heading.start for heading in headings]
    for heading in reversed(headings[: bisect_left(starts, position)]):
        if level is None or heading.level == level:
            return heading
    return None


def to_utf16(text: str, index: int) -> int:
    """The position in UTF-16 units of the Python string index ``index``."""
    return len(text[:index].encode("utf-16-le", errors="surrogatepass")) // 2


def from_utf16(text: str, position: int) -> int:
    """The Python string index of the UTF-16 position ``position``.

    A position in the middle of a pair of units gives the index of that character.
    """
    units = 0
    for index, char in enumerate(text):
        if units >= position:
            return index
        units += 2 if ord(char) > 0xFFFF else 1
        if units > position:
            return index
    return len(text)
