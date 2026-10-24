"""How a number of tokens is written: exact below a million, rounded above, in both languages."""

from collections.abc import Iterator

import pytest

from wxclaude.core.numbers import format_tokens
from wxclaude.i18n import install

pytestmark = pytest.mark.unit


@pytest.fixture
def french() -> Iterator[None]:
    install("fr")
    yield
    install("en")  # no catalog for it: the message ids, in English


@pytest.mark.parametrize(
    ("count", "english", "french_text"),
    [
        (0, "0", "0"),
        (123_456, "123456", "123456"),
        (999_999, "999999", "999999"),
        (1_000_000, "1.0 million", "1,0 million"),
        (1_500_000, "1.5 million", "1,5 million"),
        (1_949_999, "1.9 million", "1,9 million"),
        (1_950_000, "2.0 million", "2,0 millions"),
        (9_949_999, "9.9 million", "9,9 millions"),
        (9_960_000, "10 million", "10 millions"),
        (10_000_000, "10 million", "10 millions"),
        (721_582_690, "722 million", "722 millions"),
        (999_400_000, "999 million", "999 millions"),
        (999_600_000, "1.0 billion", "1,0 milliard"),
        (1_234_000_000, "1.2 billion", "1,2 milliard"),
        (2_000_000_000, "2.0 billion", "2,0 milliards"),
        (9_949_000_000, "9.9 billion", "9,9 milliards"),
        (9_960_000_000, "10 billion", "10 milliards"),
        (12_000_000_000, "12 billion", "12 milliards"),
        (1_500_000_000_000, "1500 billion", "1500 milliards"),
    ],
)
def test_a_number_of_tokens_is_written_short(
    count: int, english: str, french_text: str, request: pytest.FixtureRequest
) -> None:
    assert format_tokens(count) == english
    request.getfixturevalue("french")
    assert format_tokens(count) == french_text
