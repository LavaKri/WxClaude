"""The script that turns the Markdown help text into the HTML pages (``MakeHelp/make_help.py``)."""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = pytest.mark.unit

SCRIPT = Path(__file__).resolve().parent.parent / "MakeHelp" / "make_help.py"


def _script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("make_help", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_page_is_simple_html_with_the_language_and_the_title() -> None:
    page = _script().render_page("# Help & more\n\n## Part\n\ntext `x`\n", "fr")
    assert '<html lang="fr">' in page
    assert "<title>Help &amp; more</title>" in page
    assert "<h2>Part</h2>" in page
    assert "<code>x</code>" in page
    assert "<style" not in page
    assert "<script" not in page


def test_the_page_is_written_as_the_language_html_in_the_folder(tmp_path: Path) -> None:
    source = tmp_path / "Aide.md"
    source.write_text("# Aide\n\nTexte.\n", encoding="utf-8")
    page = _script().make_help(source, "fr", tmp_path / "help")
    assert page == tmp_path / "help" / "fr.html"
    assert "<h1>Aide</h1>" in page.read_text(encoding="utf-8")


def test_the_real_help_text_can_be_converted(tmp_path: Path) -> None:
    script = _script()
    page = script.make_help(script.DEFAULT_SOURCE, "fr", tmp_path)
    assert "<h2>" in page.read_text(encoding="utf-8")
