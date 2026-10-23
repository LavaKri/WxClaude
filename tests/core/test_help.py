from pathlib import Path

import pytest

from wxclaude.core.errors import HelpError
from wxclaude.core.help import help_page

pytestmark = pytest.mark.unit


def _folder(tmp_path: Path, *languages: str) -> Path:
    for language in languages:
        (tmp_path / f"{language}.html").write_text("<p>x</p>", encoding="utf-8")
    return tmp_path


def test_each_language_has_its_page(tmp_path: Path) -> None:
    folder = _folder(tmp_path, "fr", "en")
    assert help_page("fr", folder).name == "fr.html"
    assert help_page("en", folder).name == "en.html"


def test_an_unknown_language_falls_back_on_english(tmp_path: Path) -> None:
    assert help_page("de", _folder(tmp_path, "fr", "en")).name == "en.html"


def test_without_a_page_the_error_says_so(tmp_path: Path) -> None:
    with pytest.raises(HelpError):
        help_page("fr", _folder(tmp_path, "de"))
