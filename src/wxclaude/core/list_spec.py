"""What a list dialog shows: only data, nothing of the interface library."""

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(slots=True)
class ListSpec:
    """The content of a list dialog (``ui/list_dialog.py``).

    ``lines`` are the lines of the list; ``details`` has one text per line, or is None when the
    dialog has no details field. A label is the visible text (with its access key), a name is what
    a screen reader announces. ``selection`` is the index of the line selected at the start.
    """

    title: str
    list_label: str
    list_name: str
    lines: Sequence[str]
    details: Sequence[str] | None = None
    details_label: str = ""
    details_name: str = ""
    selection: int = 0
