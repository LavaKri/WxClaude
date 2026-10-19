"""Workspaces (working folders) and the list of recently opened ones."""

import os
from pathlib import Path

from wxclaude.i18n import _

MAX_RECENT = 10


def add_recent(recent: list[str], folder: Path) -> list[str]:
    """``folder`` moved to the front of ``recent`` (no duplicate), limited to ``MAX_RECENT``."""
    path = str(folder)
    others = [item for item in recent if item.lower() != path.lower()]
    return [path, *others][:MAX_RECENT]


def remove_missing(recent: list[str]) -> list[str]:
    """``recent`` without the folders that no longer exist."""
    return [item for item in recent if Path(item).is_dir()]


def workspace_label(folder: str) -> str:
    """How a workspace is listed: its name, then where it is (``WxClaude, from C:\\Dev\\``)."""
    name, parent = describe(folder)
    return _("{name}, from {parent}").format(name=name, parent=parent) if parent else name


def describe(folder: str) -> tuple[str, str]:
    """Name of ``folder`` and its parent path (ending with a separator, empty for a drive root)."""
    path = Path(folder)
    name = path.name or str(path)
    parent = "" if path.parent == path else str(path.parent).rstrip("\\/") + os.sep
    return name, parent
