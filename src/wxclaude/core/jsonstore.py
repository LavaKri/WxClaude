"""Reading and writing the JSON files of the application without losing them.

A file is written to a temporary file of the same folder and then moved over the old one, so a
crash never leaves a half-written file; the last valid version is kept as ``<name>.bak``. A file
that cannot be read is renamed ``<name>.corrupt``, the backup is tried, and the caller is told what
happened (``ReadResult.warning``) so that the user knows.
"""

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from wxclaude.core.errors import JsonStoreError


@dataclass(frozen=True, slots=True)
class ReadResult:
    """The content of a file (None: nothing usable, start from the defaults) and what happened."""

    data: dict[str, object] | None
    warning: str = ""


def _backup_path(path: Path) -> Path:
    return path.with_name(path.name + ".bak")


def _parse(path: Path) -> dict[str, object]:
    """The JSON object in ``path``; raises ``OSError``, ``ValueError`` (also bad JSON)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("the content is not a JSON object")
    return data


def _is_readable(path: Path) -> bool:
    """Does ``path`` hold a JSON object? (False also when it does not exist.)"""
    try:
        _parse(path)
    except OSError, ValueError:
        return False
    return True


def read_json(path: Path) -> ReadResult:
    """Read ``path``; a missing file is not an error, a damaged one is set aside."""
    backup = _backup_path(path)
    if not path.exists():
        return ReadResult(None)
    try:
        return ReadResult(_parse(path))
    except (OSError, ValueError) as error:
        reason = f"Cannot read {path}: {error}."
    moved = path.with_name(path.name + ".corrupt")
    try:
        os.replace(path, moved)
        reason += f" The file was kept as {moved.name}."
    except OSError as error:
        reason += f" It could not be set aside: {error}."
    if backup.exists():
        try:
            return ReadResult(_parse(backup), reason + " The last backup was used.")
        except (OSError, ValueError) as error:
            reason += f" The backup cannot be read either: {error}."
    return ReadResult(None, reason + " The default values were used.")


def write_json(path: Path, data: dict[str, object], *, backup: bool = True) -> None:
    """Write ``data`` to ``path`` atomically; raises ``JsonStoreError`` if it cannot be done.

    ``backup=False`` leaves no ``.bak`` next to the file (for files that are not ours).
    """
    temporary = path.with_name(path.name + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with temporary.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        if backup and _is_readable(path):  # never replace a good backup with a bad file
            shutil.copyfile(path, _backup_path(path))
        os.replace(temporary, path)
    except OSError as error:
        raise JsonStoreError(f"Cannot write {path}: {error}") from error
