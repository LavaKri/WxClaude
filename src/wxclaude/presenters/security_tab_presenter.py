"""The tab "Security" of the Workspace settings: the trust of the folder and its watched files.

What the user decides here applies at once and is saved at once (the approval and the list are
WxClaude's own files, not part of what OK writes): the check box *Trusted folder*, a check box for
each watched file, accepting the change of a file, adding a file to the list or taking it out.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from wxclaude.core.errors import JsonStoreError, WatchError
from wxclaude.core.security.watch import DEFAULT_FILES, FileState, FileStatus, WatchedFiles
from wxclaude.i18n import _
from wxclaude.presenters.security_presenter import SecurityPresenter


class SecurityTabView(Protocol):
    """What the presenter asks of the tab."""

    def show_trusted(self, trusted: bool) -> None:
        """The state of the check box *Trusted folder*."""
        ...

    def show_max_turns(self, turns: int) -> None:
        """The limit of turns of a message (0: no limit)."""
        ...

    def show_files(self, lines: list[str], watched: list[bool], selected: int) -> None:
        """The watched files, one line each with its check box, and the one selected (-1: none)."""
        ...

    def show_explanation(self, text: str) -> None:
        """The read-only text about the restricted mode and its risks."""
        ...

    def show_actions(self, can_accept: bool, can_forget: bool) -> None:
        """Which of *Accept the change* and *Remove from the list* can be used."""
        ...

    def confirm_approval(self) -> bool:
        """Ask whether to approve the folder, with what that means (No by default)."""
        ...

    def ask_file(self, folder: Path) -> Path | None:
        """Ask for a file of ``folder`` to watch. None: cancelled."""
        ...

    def show_error(self, message: str) -> None:
        """Tell the user that something failed."""
        ...


class SecurityTabPresenter:
    """The trust and the watched files of the current workspace."""

    def __init__(self, view: SecurityTabView, security: SecurityPresenter, workspace: Path) -> None:
        self._view = view
        self._security = security
        self._workspace = workspace
        self._statuses: list[FileStatus] = []
        self._selected = -1
        view.show_explanation(self.explanation())
        self.refresh()

    @staticmethod
    def explanation() -> str:
        """What the two states mean, and what to be careful about."""
        return "\n".join(
            [
                _(
                    "Approved folder: Claude uses the hooks, the settings and the servers of the "
                    "project, as Claude Code does in a terminal."
                ),
                _(
                    "Restricted folder: all of that is ignored, the CLAUDE.md, the commands and "
                    "the agents of the project are not loaded, and Claude cannot act without "
                    "your permission. It can still read the project, so you can have it "
                    "examined first."
                ),
                _(
                    "Approve only a folder you trust: a hook runs a command on your computer, "
                    "and a file of the project can send what you type to another server."
                ),
                _(
                    "The watched files are compared with what you approved each time the folder is "
                    "opened and this dialog is; a change is shown to you before anything else."
                ),
            ]
        )

    def select(self, index: int) -> None:
        """The line at ``index`` is selected (-1: none)."""
        self._selected = index
        self._show_actions()

    def set_trusted(self, trusted: bool) -> None:
        """Approve the folder (the files as they are become the reference) or restrict it."""
        if trusted:
            if self._view.confirm_approval():
                self._security.approve()
        else:
            self._security.restrict()
        self.refresh()

    def set_max_turns(self, turns: int) -> None:
        """Limit the turns of a message in this workspace (0: no limit)."""
        self._security.set_max_turns(turns)

    def set_watched(self, index: int, watched: bool) -> None:
        """Watch the file at ``index`` or stop watching it."""
        if 0 <= index < len(self._statuses):
            self._run(lambda: self._watch(self._statuses[index].path, watched))

    def accept(self) -> None:
        """Take the selected file as it is now as the approved one."""
        status = self._status()
        if status is not None and status.state in _CHANGES:
            self._run(lambda: self._files().approve([status.path]))

    def add_file(self) -> None:
        """Ask for a file of the workspace and watch it."""
        chosen = self._view.ask_file(self._workspace)
        if chosen is None:
            return
        try:
            relative = chosen.resolve().relative_to(self._workspace.resolve()).as_posix()
        except ValueError:
            self._view.show_error(_("Only a file inside the workspace can be watched."))
            return
        self._run(lambda: self._watch(relative, True))

    def forget(self) -> None:
        """Take a file the user added out of the list (the default files stay)."""
        status = self._status()
        if status is not None and status.path not in DEFAULT_FILES:
            self._run(lambda: self._files().forget(status.path))

    def refresh(self) -> None:
        """Show the state again (also after a change made elsewhere)."""
        state = self._security.state
        self._view.show_trusted(state is not None and state.trusted)
        self._view.show_max_turns(0 if state is None else state.max_turns)
        try:
            self._statuses = self._files().statuses()
        except WatchError as error:
            self._statuses = []
            self._view.show_error(str(error))
        self._selected = min(self._selected, len(self._statuses) - 1)
        self._view.show_files(
            [status.text() for status in self._statuses],
            [status.watched for status in self._statuses],
            self._selected,
        )
        self._show_actions()

    # -- inside ---------------------------------------------------------------------------

    def _files(self) -> WatchedFiles:
        guard = self._security.guard
        assert guard is not None, "the tab only exists for an open workspace"
        return guard

    def _watch(self, relative: str, watched: bool) -> None:
        self._files().set_watched(relative, watched)

    def _status(self) -> FileStatus | None:
        return self._statuses[self._selected] if 0 <= self._selected < len(self._statuses) else None

    def _run(self, action: Callable[[], None]) -> None:
        try:
            action()
        except (WatchError, JsonStoreError) as error:
            self._view.show_error(str(error))
        self.refresh()

    def _show_actions(self) -> None:
        status = self._status()
        self._view.show_actions(
            status is not None and status.state in _CHANGES,
            status is not None and status.path not in DEFAULT_FILES,
        )


_CHANGES = frozenset({FileState.CHANGED, FileState.ADDED, FileState.REMOVED})
