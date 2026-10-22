"""The layers of the code: the model (``core``) and the presenters never import wx."""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

PACKAGE = Path(__file__).resolve().parent.parent / "src" / "wxclaude"
_WX_IMPORT = re.compile(r"^\s*(import wx\b|from wx\b)", re.MULTILINE)


@pytest.mark.parametrize("layer", ["core", "presenters"])
def test_the_layer_does_not_import_wx(layer: str) -> None:
    offenders = [
        path.name
        for path in sorted((PACKAGE / layer).glob("*.py"))
        if _WX_IMPORT.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []
