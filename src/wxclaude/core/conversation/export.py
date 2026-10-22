"""Export of a conversation to a text file."""

from pathlib import Path

from wxclaude.core.errors import ExportError


def export_text(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` as UTF-8."""
    try:
        path.write_text(text, encoding="utf-8")
    except OSError as error:
        raise ExportError(f"Cannot write {path}: {error}") from error
