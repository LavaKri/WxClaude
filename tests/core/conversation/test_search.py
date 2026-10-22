import pytest

from wxclaude.core.conversation.search import (
    Match,
    SearchOptions,
    find_next,
    find_previous,
    line_at,
)

pytestmark = pytest.mark.unit

TEXT = "one two\nTwo three\ntwo\n"


def test_next_finds_the_first_occurrence_from_the_position() -> None:
    options = SearchOptions("two")
    assert find_next(TEXT, options, 0) == Match(4, 7)
    assert find_next(TEXT, options, 5) == Match(8, 11)
    assert find_next(TEXT, options, 12) == Match(18, 21)
    assert find_next(TEXT, options, 19) is None  # no wrapping


def test_previous_finds_the_last_occurrence_before_the_position() -> None:
    options = SearchOptions("two")
    assert find_previous(TEXT, options, len(TEXT)) == Match(18, 21)
    assert find_previous(TEXT, options, 18) == Match(8, 11)
    assert find_previous(TEXT, options, 8) == Match(4, 7)
    assert find_previous(TEXT, options, 4) is None


def test_case_is_ignored_unless_asked() -> None:
    assert find_next(TEXT, SearchOptions("TWO", match_case=True), 0) is None
    assert find_next(TEXT, SearchOptions("Two", match_case=True), 0) == Match(8, 11)
    assert find_next("École", SearchOptions("école"), 0) == Match(0, 5)


def test_whole_words_do_not_match_inside_a_word() -> None:
    options = SearchOptions("is", whole_word=True)
    assert find_next("this is it", options, 0) == Match(5, 7)
    assert find_next("this island", options, 0) is None
    assert find_next("this island", SearchOptions("is"), 0) == Match(2, 4)


def test_a_term_with_special_characters_is_searched_literally() -> None:
    assert find_next("a.b a+b (x)", SearchOptions("a+b"), 0) == Match(4, 7)
    assert find_next("a.b axb", SearchOptions("a.b"), 0) == Match(0, 3)
    assert find_next("f(x) and g(y)", SearchOptions("(x)", whole_word=True), 0) == Match(1, 4)


def test_an_empty_term_finds_nothing() -> None:
    assert find_next(TEXT, SearchOptions(""), 0) is None
    assert find_previous(TEXT, SearchOptions(""), len(TEXT)) is None


def test_positions_are_python_indexes_after_an_emoji() -> None:
    text = "a😀 b😀 c"
    assert find_next(text, SearchOptions("c"), 0) == Match(6, 7)


def test_line_at_gives_the_whole_line() -> None:
    assert line_at(TEXT, 5) == "one two"
    assert line_at(TEXT, 8) == "Two three"
    assert line_at(TEXT, 18) == "two"
    assert line_at("no break", 3) == "no break"
    assert line_at("a\r\nb", 0) == "a"
