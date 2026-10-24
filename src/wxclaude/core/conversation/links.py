"""The links of a Markdown text and where they start, found in the text the field shows.

A link is ``[text](address)`` or ``<address>``, as CommonMark reads them: links in code (spans and
fenced blocks), escaped brackets, images and bare addresses are not links. They are looked for
line by line, so a link that runs over a line break, or one written with a reference
(``[text][name]``), is not found. The offsets are Python string indexes of the text.
"""

from collections.abc import Callable
from dataclasses import dataclass

from markdown_it import MarkdownIt
from markdown_it.rules_inline import StateInline
from markdown_it.rules_inline import autolink as _autolink
from markdown_it.rules_inline import link as _link

from wxclaude.core.conversation.code_blocks import lines_with_code_mark


@dataclass(frozen=True, slots=True)
class LinkPlace:
    """A link: the offset where it starts (its ``[`` or ``<``), its text and its address."""

    start: int
    text: str
    url: str


def _recording(
    rule: Callable[[StateInline, bool], bool], starts: list[int]
) -> Callable[[StateInline, bool], bool]:
    """``rule`` (a rule of the inline parser) noting where each link it finds starts."""

    def tokenize(state: StateInline, silent: bool) -> bool:
        start = state.pos
        found = rule(state, silent)
        if found and not silent:
            starts.append(start)
        return found

    return tokenize


def _links_of_line(line: str, parser: MarkdownIt, starts: list[int]) -> list[tuple[int, str, str]]:
    starts.clear()
    tokens = parser.parseInline(line)
    children = tokens[0].children if tokens and tokens[0].children else []
    found: list[tuple[int, str, str]] = []
    href: str | None = None
    text: list[str] = []
    for child in children:
        if child.type == "link_open":
            href, text = str(child.attrGet("href") or ""), []
        elif child.type == "link_close" and href is not None:
            found.append((starts[len(found)], "".join(text).strip(), href))
            href = None
        elif href is not None and child.type in ("text", "code_inline"):
            text.append(child.content)
    return found


def link_places(text: str) -> list[LinkPlace]:
    """The links of ``text`` in document order, with the offset where each starts."""
    starts: list[int] = []
    parser = MarkdownIt("commonmark")
    parser.inline.ruler.at("link", _recording(_link, starts))
    parser.inline.ruler.at("autolink", _recording(_autolink, starts))
    places: list[LinkPlace] = []
    for offset, line, is_code in lines_with_code_mark(text):
        if is_code or ("[" not in line and "<" not in line):
            continue
        for start, label, url in _links_of_line(line, parser, starts):
            places.append(LinkPlace(offset + start, label, url))
    return places
