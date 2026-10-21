import pytest

from wxclaude.core.labels import accessible_name

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
