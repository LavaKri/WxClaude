import re
from pathlib import Path

import pytest

from wxclaude.core.help import help_source, render_help, write_help_page

pytestmark = pytest.mark.unit


def test_each_language_has_its_source() -> None:
    assert help_source("fr").name == "fr.md"
    assert help_source("en").name == "en.md"


def test_an_unknown_language_falls_back_on_english() -> None:
    assert help_source("de").name == "en.md"


def test_both_sources_have_the_same_structure() -> None:
    def levels(language: str) -> list[int]:
        text = help_source(language).read_text(encoding="utf-8")
        return [len(match) for match in re.findall(r"^(#+) ", text, re.MULTILINE)]

    assert levels("fr") == levels("en")


def test_the_page_is_html_with_the_language_and_the_title() -> None:
    page = render_help("# Help & more\n\n## Part\n\ntext `x`\n", "fr")
    assert '<html lang="fr">' in page
    assert "<title>Help &amp; more</title>" in page
    assert "<h2>Part</h2>" in page
    assert "<code>x</code>" in page


def test_the_page_is_written_in_the_temporary_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    page = write_help_page("de")
    assert page == tmp_path / "wxclaude-help" / "en.html"
    assert '<html lang="en">' in page.read_text(encoding="utf-8")
