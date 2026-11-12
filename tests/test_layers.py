"""The layers of the code: imports go one way, ``ui`` -> ``presenters`` -> ``core``.

The model (``core``) and the presenters never import wx; ``core`` never imports a presenter or
the interface; a presenter never imports the interface.
"""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

PACKAGE = Path(__file__).resolve().parent.parent / "src" / "wxclaude"
_WX_IMPORT = re.compile(r"^\s*(import wx\b|from wx\b)", re.MULTILINE)


def _import_of(package: str) -> re.Pattern[str]:
    return re.compile(rf"^\s*(import|from) wxclaude\.{package}\b", re.MULTILINE)


# For each layer, the layers it must not import.
FORBIDDEN_LAYERS = [
    ("core", "presenters"),
    ("core", "ui"),
    ("presenters", "ui"),
]


def _offenders(layer: str, pattern: re.Pattern[str]) -> list[str]:
    return [
        str(path.relative_to(PACKAGE))
        for path in sorted((PACKAGE / layer).rglob("*.py"))
        if pattern.search(path.read_text(encoding="utf-8"))
    ]


@pytest.mark.parametrize("layer", ["core", "presenters"])
def test_the_layer_does_not_import_wx(layer: str) -> None:
    assert _offenders(layer, _WX_IMPORT) == []


@pytest.mark.parametrize(("layer", "above"), FORBIDDEN_LAYERS)
def test_a_layer_does_not_import_the_layers_above_it(layer: str, above: str) -> None:
    assert _offenders(layer, _import_of(above)) == []


def test_the_import_patterns_find_what_they_look_for() -> None:
    """The checks above would pass for ever with a pattern that matches nothing."""
    assert _import_of("ui").search("from wxclaude.ui.main_window import MainWindow")
    assert _import_of("ui").search("    import wxclaude.ui.fields")
    assert not _import_of("ui").search("from wxclaude.core.errors import WxClaudeError")
    assert not _import_of("ui").search("from wxclaude.uifoo import x")
    assert _WX_IMPORT.search("import wx.adv")
    assert not _WX_IMPORT.search("from wxclaude.ui import x")
