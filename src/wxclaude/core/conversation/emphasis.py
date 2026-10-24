"""Remove the Markdown marks of bold and italic from a text, keeping everything else.

Only real emphasis is touched: ``**bold**``, ``__bold__``, ``*italic*`` and ``_italic_``, as
CommonMark reads them. A star that is only a star (``2 * 3``, ``*.py``, a bullet), ``snake_case``,
code (spans and fenced blocks), links and escaped marks stay as they are. The number of lines does
not change, so a position in a line of the result is a position in the same line of the source.
Emphasis is looked for line by line: one that runs over a line break keeps its marks.
"""

from collections.abc import Callable

from markdown_it import MarkdownIt
from markdown_it.rules_inline import StateInline
from markdown_it.rules_inline import emphasis as _emphasis

from wxclaude.core.conversation.code_blocks import lines_with_code_mark

_EMPHASIS_TOKENS = frozenset({"em_open", "em_close", "strong_open", "strong_close"})


def _recording_tokenizer(positions: dict[int, int]) -> Callable[[StateInline, bool], bool]:
    """The emphasis rule of the parser, noting where in the line each mark it sees starts."""

    def tokenize(state: StateInline, silent: bool) -> bool:
        start = state.pos
        found = _emphasis.tokenize(state, silent)
        if found:
            length = state.pos - start
            for offset in range(length):  # one token per mark, the last ones pushed
                positions[len(state.tokens) - length + offset] = start + offset
        return found

    return tokenize


def _marks_in(line: str) -> list[int]:
    """The positions in ``line`` of the characters that are marks of bold or italic."""
    positions: dict[int, int] = {}
    parser = MarkdownIt("commonmark")
    parser.inline.ruler.at("emphasis", _recording_tokenizer(positions))
    parser.disable("fragments_join")  # it would renumber the tokens
    state = StateInline(line, parser, {}, [])
    parser.inline.tokenize(state)
    for rule in parser.inline.ruler2.getRules(""):
        rule(state)
    return [
        position
        for index, position in positions.items()
        if state.tokens[index].type in _EMPHASIS_TOKENS
        # the second character of ``**`` is a text token emptied by the parser
        or (state.tokens[index].type == "text" and state.tokens[index].content == "")
    ]


def remove_emphasis(text: str) -> str:
    """``text`` without the marks of bold and italic (see the module)."""
    lines: list[str] = []
    for _offset, line, is_code in lines_with_code_mark(text):
        if not is_code and ("*" in line or "_" in line):
            marks = set(_marks_in(line))
            line = "".join(char for index, char in enumerate(line) if index not in marks)
        lines.append(line)
    return "\n".join(lines)
