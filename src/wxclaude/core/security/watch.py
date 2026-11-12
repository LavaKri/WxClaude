"""The files of a workspace that can change what the CLI does, and their approved state.

For each file of the list (``docs/security.md``, "Watched files") WxClaude keeps, in the state of
the workspace, the SHA-256 of the content the user approved, and, in ``workspaces/<hash>.watch/``,
a copy of that content with its secrets masked (``sensitive.py``). Comparing the files now with
that record gives the changes. ``WatchedFiles`` is also the one door through which the application
writes ``.claude/settings*.json``: it refuses to write over a change made from outside, and records
what it wrote so that its own writes never raise an alert.
"""

import difflib
import enum
import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from wxclaude.core.config.jsonstore import write_json
from wxclaude.core.config.workspace_state import WatchRecord, WorkspaceState
from wxclaude.core.errors import ClaudeSettingsError, WatchError
from wxclaude.core.security.sensitive import mask_json_text
from wxclaude.i18n import N_, _

DEFAULT_FILES = (".claude/settings.json", ".claude/settings.local.json", ".mcp.json")
# All the files under these folders: a file added or removed is a change too.
DEFAULT_FOLDERS = (".claude/agents", ".claude/skills", ".claude/commands")

_CHUNK = 1 << 16
_COPY_HASH_BYTES = 8


class FileState(enum.Enum):
    """How a file stands against what was approved."""

    UNCHANGED = "unchanged"
    CHANGED = "changed"
    ADDED = "added"  # it did not exist when approved
    REMOVED = "removed"  # it existed when approved
    ABSENT = "absent"  # it did not exist then and does not now


_STATE_LABELS = {
    FileState.UNCHANGED: N_("unchanged"),
    FileState.CHANGED: N_("changed"),
    FileState.ADDED: N_("added"),
    FileState.REMOVED: N_("removed"),
    FileState.ABSENT: N_("absent"),
}
_CHANGES = frozenset({FileState.CHANGED, FileState.ADDED, FileState.REMOVED})


@dataclass(frozen=True, slots=True)
class FileStatus:
    """One file of the list: its path relative to the workspace (with ``/``) and its state."""

    path: str
    state: FileState
    watched: bool

    @property
    def is_change(self) -> bool:
        """Is this a change the user is told about? (Only for a file that is watched.)"""
        return self.watched and self.state in _CHANGES

    def text(self) -> str:
        """The line of a list: ``.mcp.json, changed`` (``, not watched`` when it is not)."""
        line = _("{path}, {state}").format(path=self.path, state=_(_STATE_LABELS[self.state]))
        return line if self.watched else _("{line}, not watched").format(line=line)


class ExternalChangeError(ClaudeSettingsError):
    """A file was changed from outside since it was approved: it is not written over."""

    def __init__(self, statuses: list[FileStatus]) -> None:
        paths = ", ".join(status.path for status in statuses)
        super().__init__(
            _("{paths} changed since you approved it and was not modified.").format(paths=paths)
        )
        self.statuses = statuses


def file_hash(path: Path) -> str:
    """The SHA-256 of the file, empty if it does not exist; raises ``WatchError`` if it cannot be
    read."""
    if not path.is_file():
        return ""
    digest = hashlib.sha256()
    try:
        with path.open("rb") as file:
            while chunk := file.read(_CHUNK):
                digest.update(chunk)
    except OSError as error:
        raise WatchError(f"Cannot read {path}: {error}") from error
    return digest.hexdigest()


def _copy_name(relative: str) -> str:
    """The name of the copy of a file: a hash of its path (two folders may hold the same name)."""
    short = hashlib.blake2b(relative.lower().encode("utf-8"), digest_size=_COPY_HASH_BYTES)
    return f"{short.hexdigest()}-{relative.rsplit('/', 1)[-1]}.bak"


def masked_content(path: Path) -> str | None:
    """The text of ``path`` that may be copied: a JSON file with its secrets masked, any other file
    as it is. None when there is nothing to copy: no file, or a ``.json`` file that cannot be
    parsed and so cannot be masked."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if path.suffix.lower() == ".json":
        return mask_json_text(text)
    return text


def _write_text(path: Path, text: str) -> None:
    """Write ``text`` atomically (a temporary file of the same folder, then a move)."""
    temporary = path.with_name(path.name + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(path)
    except OSError as error:
        raise WatchError(f"Cannot write {path}: {error}") from error


class WatchedFiles:
    """The files of one workspace that are watched, against the state that was approved."""

    def __init__(self, workspace: Path, state: WorkspaceState) -> None:
        self._workspace = workspace
        self._state = state

    @property
    def approved(self) -> bool:
        """Has the user approved the files of this workspace? (Without it, nothing is compared.)"""
        return bool(self._state.watch)

    def paths(self) -> list[str]:
        """The files of the list: the default ones, those found in the default folders, and those
        the state already knows (a file the user added, or one that was removed)."""
        found = set(DEFAULT_FILES) | set(self._state.watch)
        for folder in DEFAULT_FOLDERS:
            root = self._workspace / folder
            if root.is_dir():
                found.update(
                    file.relative_to(self._workspace).as_posix()
                    for file in root.rglob("*")
                    if file.is_file()
                )
        return sorted(found)

    def present(self) -> list[str]:
        """The files of the list that exist now."""
        return [path for path in self.paths() if (self._workspace / path).is_file()]

    def statuses(self) -> list[FileStatus]:
        """Every file of the list with its state; raises ``WatchError`` if one cannot be read."""
        return [self._status(path) for path in self.paths()]

    def changes(self) -> list[FileStatus]:
        """The watched files that changed. Empty as long as nothing was approved."""
        if not self.approved:
            return []
        return [status for status in self.statuses() if status.is_change]

    def _status(self, relative: str) -> FileStatus:
        current = file_hash(self._workspace / relative)
        record = self._state.watch.get(relative)
        approved = record.sha256 if record else ""
        if current == approved:
            state = FileState.UNCHANGED if current else FileState.ABSENT
        elif not approved:
            state = FileState.ADDED
        elif not current:
            state = FileState.REMOVED
        else:
            state = FileState.CHANGED
        return FileStatus(relative, state, record.watched if record else True)

    def diff(self, relative: str) -> list[str]:
        """The lines that differ between the approved copy and the file now (masked, so a secret
        that changed shows as another hash, never as content). A file that did not exist when
        approved is all added lines. Empty when the approved copy is not known."""
        record = self._state.watch.get(relative)
        folder = self._state.watch_dir
        if record is None or not record.sha256:
            approved: list[str] = []  # there was no file, so there is no copy either
        elif folder is None:
            return []
        else:
            try:
                approved = (folder / _copy_name(relative)).read_text(encoding="utf-8").splitlines()
            except OSError:
                return []
        current = masked_content(self._workspace / relative)
        lines = [] if current is None else current.splitlines()
        return list(difflib.unified_diff(approved, lines, "approved", "now", lineterm=""))

    # -- what the user decides ------------------------------------------------------------

    def approve(self, paths: Iterable[str] | None = None) -> None:
        """Take the files as they are now as the approved state (all of them if ``paths`` is None).

        Raises ``WatchError`` if a file cannot be read or a copy written, ``JsonStoreError`` if the
        state cannot be written.
        """
        for relative in paths if paths is not None else self.paths():
            self._record(relative)
        self._state.save()

    def set_watched(self, relative: str, watched: bool) -> None:
        """Watch the file or stop watching it (it is still hashed and copied). A file that is
        not known yet is added to the list as it is now."""
        if relative not in self._state.watch:
            self._record(relative)
        record = self._state.watch.get(relative)
        if record is not None:  # None: a file that does not exist cannot be added
            record.watched = watched
            self._state.save()

    def forget(self, relative: str) -> None:
        """Take a file the user added out of the list (the default files stay in it)."""
        if relative in DEFAULT_FILES:
            return
        if self._state.watch.pop(relative, None) is not None:
            self._remove_copy(relative)
            self._state.save()

    def _record(self, relative: str) -> None:
        """Record the hash and the copy of a file as it is now (no save of the state).

        A file that does not exist is kept, with an empty hash, only if the list always holds it
        (``DEFAULT_FILES``); any other is dropped, which is how an accepted removal ends.
        """
        sha256 = file_hash(self._workspace / relative)
        if not sha256 and relative not in DEFAULT_FILES:
            self._state.watch.pop(relative, None)
            self._remove_copy(relative)
            return
        record = self._state.watch.setdefault(relative, WatchRecord())
        record.sha256 = sha256
        self._write_copy(relative)

    def _write_copy(self, relative: str) -> None:
        folder = self._state.watch_dir
        if folder is None:
            return
        text = masked_content(self._workspace / relative)
        if text is None:
            self._remove_copy(relative)
        else:
            _write_text(folder / _copy_name(relative), text)

    def _remove_copy(self, relative: str) -> None:
        folder = self._state.watch_dir
        if folder is not None:
            (folder / _copy_name(relative)).unlink(missing_ok=True)

    # -- the one door for writing a settings file -----------------------------------------

    def _relative(self, path: Path) -> str | None:
        try:
            return path.relative_to(self._workspace).as_posix()
        except ValueError:
            return None

    def verify(self, path: Path) -> None:
        """Raise ``ExternalChangeError`` if ``path`` changed since it was approved."""
        relative = self._relative(path)
        if relative is None or relative not in self._state.watch:
            return
        status = self._status(relative)
        if status.state in _CHANGES:
            raise ExternalChangeError([status])

    def write_json(self, path: Path, data: dict[str, object]) -> None:
        """Write a JSON file of the workspace, after checking that nobody changed it since it was
        approved, and record what was written as the approved state.

        Raises ``ExternalChangeError`` (nothing is written), ``JsonStoreError`` or ``WatchError``.
        """
        self.verify(path)
        write_json(path, data, backup=False)
        relative = self._relative(path)
        if relative is not None and self.approved:
            self._record(relative)
            self._state.save()
