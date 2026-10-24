import pytest

from wxclaude.core.labels import accessible_name, shorten

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("label", "name"),
    [
        ("&Tools", "Tools"),
        ("Rule to a&dd", "Rule to add"),
        ("Re&fresh the conversation", "Refresh the conversation"),
        ("Tools", "Tools"),
        ("", ""),
        ("Q&&A", "Q&A"),
        ("&&", "&"),
        ("Copy&", "Copy"),
        ("&Outils utilisés", "Outils utilisés"),
        ("Ouvrir &dossier…", "Ouvrir dossier…"),
    ],
)
def test_the_access_key_marker_is_removed(label: str, name: str) -> None:
    assert accessible_name(label) == name


def test_a_text_within_the_limit_is_kept() -> None:
    assert shorten("Ready", 200) == "Ready"
    assert shorten("x" * 200, 200) == "x" * 200
    assert shorten("", 200) == ""


def test_a_longer_text_is_cut_to_the_limit_with_an_ellipsis() -> None:
    result = shorten("y" * 201, 200)
    assert len(result) == 200
    assert result == "y" * 199 + "…"


def test_the_space_before_the_ellipsis_is_dropped() -> None:
    assert shorten("one two three", 8) == "one two…"
