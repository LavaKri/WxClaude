import pytest

from wxclaude.core.conversation.blocks import BlockKind, block_starts
from wxclaude.core.conversation.links import LinkPlace, link_places

pytestmark = pytest.mark.unit


def test_links_and_autolinks_are_found_with_their_start() -> None:
    text = "See [the docs](http://x.org/a) and <https://y.org> now."
    assert link_places(text) == [
        LinkPlace(4, "the docs", "http://x.org/a"),
        LinkPlace(35, "https://y.org", "https://y.org"),
    ]
    assert text[4] == "["
    assert text[35] == "<"


def test_what_is_not_a_link_is_left_out() -> None:
    text = (
        "`[in](code)` and \\[escaped](x) and ![image](p.png)\n"
        "```\n[fenced](http://z)\n```\n"
        "bare http://w.org and [reference][r] and [just brackets] and a < b\n"
    )
    assert link_places(text) == []


def test_links_of_several_lines_have_offsets_in_the_whole_text() -> None:
    text = "one [a](u1)\n\n- item [b](u2)\n| [c](u3) | x |"
    places = link_places(text)
    assert [(p.text, text[p.start]) for p in places] == [("a", "["), ("b", "["), ("c", "[")]
    assert [p.url for p in places] == ["u1", "u2", "u3"]


def test_the_text_of_a_link_can_hold_code_and_emphasis() -> None:
    (place,) = link_places("go [the `docs` of *it*](u)")
    assert place.text == "the docs of it"


def test_a_text_without_links_has_none() -> None:
    assert link_places("") == []
    assert link_places("plain text\nsecond line") == []


def test_the_blocks_hold_the_links_with_a_label_to_say() -> None:
    text = "a [the docs](http://x) b\n<http://y>"
    links = block_starts(text)[BlockKind.LINK]
    assert [link.start for link in links] == [2, 25]
    assert [link.label for link in links] == ["the docs, http://x", "http://y"]
