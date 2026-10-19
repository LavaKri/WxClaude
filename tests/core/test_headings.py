import pytest

from wxclaude.core.headings import (
    from_utf16,
    next_heading,
    parse_headings,
    previous_heading,
    to_utf16,
)

pytestmark = pytest.mark.unit

TEXT = "# One\nbody\n\n## Two\nmore\n\nThree\n=====\nend\n"


def test_atx_and_setext_headings_are_found_with_their_offsets() -> None:
    headings = parse_headings(TEXT)
    assert [(h.level, h.title) for h in headings] == [(1, "One"), (2, "Two"), (1, "Three")]
    one, two, three = headings
    assert TEXT[one.start : one.end] == "# One"
    assert TEXT[two.start : two.end] == "## Two"
    assert TEXT[three.start : three.end] == "Three\n====="
    assert (one.body_end, two.body_end, three.body_end) == (two.start, three.start, len(TEXT))


def test_code_blocks_are_ignored() -> None:
    assert parse_headings("```\n# not a heading\n```\n\n    # nor this\n") == []


def test_heading_on_the_last_line_without_line_break() -> None:
    (heading,) = parse_headings("text\n\n# Last")
    assert (heading.title, heading.end) == ("Last", len("text\n\n# Last"))


def test_next_and_previous_heading() -> None:
    headings = parse_headings(TEXT)
    assert next_heading(headings, 0) is headings[1]
    assert next_heading(headings, -1) is headings[0]
    assert next_heading(headings, 0, level=1) is headings[2]
    assert next_heading(headings, headings[2].start) is None
    assert previous_heading(headings, headings[2].start) is headings[1]
    assert previous_heading(headings, len(TEXT), level=1) is headings[2]
    assert previous_heading(headings, 0) is None
    assert previous_heading(headings, headings[1].start, level=2) is None


def test_utf16_positions_count_two_units_for_astral_characters() -> None:
    text = "a😀b"
    assert to_utf16(text, 2) == 3
    assert to_utf16(text, 3) == 4
    assert from_utf16(text, 3) == 2
    assert from_utf16(text, 2) == 1  # in the middle of the emoji
    assert from_utf16(text, 99) == 3
