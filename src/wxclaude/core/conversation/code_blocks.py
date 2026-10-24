"""The lines of a Markdown text, with a mark on those that belong to a fenced code block."""

import re
from collections.abc import Iterator

_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


def lines_with_code_mark(text: str) -> Iterator[tuple[int, str, bool]]:
    """Each line of ``text`` as (its offset in ``text``, the line, whether it is code).

    A fenced block (three or more backticks or tildes) is code, its fences included; a closing
    fence is of the same kind and at least as long as the opening one. ``text`` uses ``\n``.
    """
    fence: str | None = None  # the opening fence of the block we are in
    offset = 0
    for line in text.split("\n"):
        opening = _FENCE.match(line)
        if fence is not None:
            if opening and opening.group(1)[0] == fence[0] and len(opening.group(1)) >= len(fence):
                fence = None
            yield offset, line, True
        elif opening:
            fence = opening.group(1)
            yield offset, line, True
        else:
            yield offset, line, False
        offset += len(line) + 1
