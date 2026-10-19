"""Searching a text: next and previous occurrence, and the line that holds one.

Positions are Python string indexes. The search does not wrap around: when there is no more
occurrence in the direction asked, ``None`` is returned and the caller says so.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SearchOptions:
    """What to look for."""

    term: str
    match_case: bool = False
    whole_word: bool = False

    def pattern(self) -> re.Pattern[str]:
        """The regular expression that matches the term literally."""
        body = re.escape(self.term)
        if self.whole_word:
            # A boundary only makes sense next to a letter, a digit or an underscore.
            before = r"(?<!\w)" if self.term[:1].isalnum() or self.term[:1] == "_" else ""
            after = r"(?!\w)" if self.term[-1:].isalnum() or self.term[-1:] == "_" else ""
            body = f"{before}{body}{after}"
        return re.compile(body, 0 if self.match_case else re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class Match:
    """An occurrence: ``start`` included, ``end`` excluded."""

    start: int
    end: int


def find_next(text: str, options: SearchOptions, position: int) -> Match | None:
    """The first occurrence that starts at ``position`` or after."""
    if not options.term:
        return None
    found = options.pattern().search(text, max(0, position))
    return Match(found.start(), found.end()) if found else None


def find_previous(text: str, options: SearchOptions, position: int) -> Match | None:
    """The last occurrence that starts before ``position``."""
    if not options.term:
        return None
    last: Match | None = None
    for found in options.pattern().finditer(text):
        if found.start() >= position:
            break
        last = Match(found.start(), found.end())
    return last


def line_at(text: str, index: int) -> str:
    """The whole line of ``text`` that holds the character ``index`` (without its line break)."""
    start = text.rfind("\n", 0, index) + 1
    end = text.find("\n", index)
    return text[start : len(text) if end < 0 else end].rstrip("\r")
