import pytest

from wxclaude.core.conversation.emphasis import remove_emphasis

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("a **bold** word", "a bold word"),
        ("a __bold__ word", "a bold word"),
        ("an *italic* word", "an italic word"),
        ("an _italic_ word", "an italic word"),
        ("***both*** here", "both here"),
        ("**bold with *italic* inside**", "bold with italic inside"),
        ("**Title:** the text", "Title: the text"),
        ("## **Heading**", "## Heading"),
        ("- **item**: detail", "- item: detail"),
        ("1. *first*", "1. first"),
        ("> **quoted**", "> quoted"),
        ("| **a** | *b* |", "| a | b |"),
        ("un **mot** et un autre **mot**", "un mot et un autre mot"),
        ("l'**été** *fautif*", "l'été fautif"),
        ("**accentué é** ok", "accentué é ok"),
    ],
)
def test_bold_and_italic_marks_are_removed(source: str, expected: str) -> None:
    assert remove_emphasis(source) == expected


@pytest.mark.parametrize(
    "source",
    [
        "2 * 3 * 4",
        "the files *.py and *.md",
        "* a bullet",
        "- a list",
        "snake_case_name and my_var_2 are not italic",
        "a_b_c",
        "an unmatched ** pair",
        "a lone * star",
        "***",
        "---",
        r"escaped \*stars\* stay",
        "`**in code**` stays",
        "``a * b`` stays",
        "[a link](http://x/_y_/z) stays",
        "<http://x/*y*> stays",
        "# A title",
        "",
        "no marks at all",
    ],
)
def test_what_is_not_emphasis_is_left_alone(source: str) -> None:
    assert remove_emphasis(source) == source


def test_a_code_block_is_left_alone() -> None:
    source = "**bold**\n```\n**not bold** and *x*\n```\n*after*"
    assert remove_emphasis(source) == "bold\n```\n**not bold** and *x*\n```\nafter"


def test_a_longer_closing_fence_and_a_tilde_fence_are_understood() -> None:
    source = "~~~\n**raw**\n~~~\n**cooked**\n````\n**raw**\n```\n**still raw**\n````\n**cooked**"
    assert remove_emphasis(source) == (
        "~~~\n**raw**\n~~~\ncooked\n````\n**raw**\n```\n**still raw**\n````\ncooked"
    )


def test_the_number_of_lines_does_not_change() -> None:
    source = "# **T**\n\n- *a*\n- b\n\n| **x** | y |\n|---|---|\n| 1 | **2** |\n"
    result = remove_emphasis(source)
    assert result.count("\n") == source.count("\n")
    assert result == "# T\n\n- a\n- b\n\n| x | y |\n|---|---|\n| 1 | 2 |\n"


def test_an_emphasis_over_a_line_break_keeps_its_marks() -> None:
    assert remove_emphasis("**one\ntwo**") == "**one\ntwo**"


def test_a_bare_dunder_name_is_bold_as_in_any_markdown_renderer() -> None:
    assert remove_emphasis("call __init__ now") == "call init now"
    assert remove_emphasis("call `__init__` now") == "call `__init__` now"
