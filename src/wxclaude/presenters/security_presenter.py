"""Trusting a folder and the files that can change what the CLI does (``docs/security.md``).

A folder is *approved* or *restricted*. In a restricted folder the CLI is launched so that it
ignores what the project supplies (hooks, ``env``, servers). The presenter keeps the state of the
current workspace, offers the approval when a folder is new, alerts when a watched file of an
approved folder changed, and is the one door through which the settings files are written
(``guard``). What is asked or shown goes through ``SecurityView``; the choices are the user's
alone.
"""

import enum
from pathlib import Path
from typing import Protocol

from wxclaude.core.config.workspace_state import WorkspaceState
from wxclaude.core.errors import JsonStoreError, WatchError
from wxclaude.core.list_spec import ListSpec
from wxclaude.core.security.watch import ExternalChangeError, FileStatus, WatchedFiles
from wxclaude.core.speech.announcements import Announce
from wxclaude.i18n import _


class ApprovalChoice(enum.Enum):
    """The answer to the offer to approve a folder."""

    APPROVE = "approve"
    KEEP_RESTRICTED = "keep_restricted"


class AlertChoice(enum.Enum):
    """The answer to the alert about changed files (no answer: decide later)."""

    ACCEPT = "accept"
    RESTRICT = "restrict"


class SecurityView(Protocol):
    """What the presenter asks of the interface."""

    def ask_approval(self, folder: Path, used_before: bool, files: list[str]) -> ApprovalChoice:
        """Offer to approve ``folder``; ``files`` are the watched files that exist in it and
        ``used_before`` says that WxClaude already worked in it."""
        ...

    def show_alert(self, spec: ListSpec) -> AlertChoice | None:
        """Show the changed files (a list, and under it the differences of the selected one) and
        let the user accept the changes or restrict the folder. None: decide later."""
        ...

    def say(self, announce: Announce, **values: object) -> None:
        """Announce, without moving the focus."""
        ...

    def show_error(self, message: str) -> None:
        """Tell the user that something failed."""
        ...


class SecurityPresenter:
    """The trust state of the current workspace."""

    def __init__(self, view: SecurityView) -> None:
        self._view = view
        self._workspace: Path | None = None
        self._state: WorkspaceState | None = None
        self._watched: WatchedFiles | None = None

    def open(self, workspace: Path, state: WorkspaceState) -> None:
        """Make ``workspace`` the current one. Nothing is shown: ``greet`` does it, later."""
        self._workspace = workspace
        self._state = state
        self._watched = WatchedFiles(workspace, state)

    # -- what the others need -------------------------------------------------------------

    @property
    def restricted(self) -> bool:
        """Must the CLI be launched in restricted mode? True until the folder is approved."""
        return self._state is not None and not self._state.trusted

    @property
    def guard(self) -> WatchedFiles | None:
        """The one door for writing the settings files of the workspace (None: no workspace)."""
        return self._watched

    @property
    def state(self) -> WorkspaceState | None:
        """What is remembered of the current workspace (None: no workspace)."""
        return self._state

    def set_max_turns(self, turns: int) -> None:
        """Limit the turns of a message in this workspace (0: no limit) and remember it."""
        if self._state is None:
            return
        self._state.max_turns = max(turns, 0)
        self._save_state()

    # -- when a workspace is opened, or a dialog that edits its files ---------------------

    def greet(self) -> None:
        """A workspace was opened: offer the approval to a folder not asked about yet, say that a
        folder is restricted, or alert about the files of an approved folder that changed."""
        state = self._state
        if state is None or self._workspace is None:
            return
        if state.trusted:
            self.check()
            return
        if not state.approval_asked:
            self._offer_approval(self._workspace, state)
        if not state.trusted:
            self._view.say(Announce.FOLDER_RESTRICTED)

    def check(self) -> None:
        """Alert about the watched files of an approved folder that changed since it was approved
        (when it is opened, and when a dialog that edits these files is)."""
        if self._state is None or self._watched is None or not self._state.trusted:
            return
        try:
            changes = self._watched.changes()
        except WatchError as error:
            self._fail(_("The watched files cannot be checked.\n{error}"), error)
            return
        if changes:
            self._alert(changes)

    def refused(self, error: ExternalChangeError) -> None:
        """A write was refused because the file changed from outside: alert, nothing was written."""
        self._alert(error.statuses)

    # -- the decisions of the user --------------------------------------------------------

    def approve(self) -> bool:
        """Approve the folder: the files as they are now become the reference. False (with the
        error shown) if that cannot be recorded."""
        if self._state is None or self._watched is None:
            return False
        self._state.trusted = True
        self._state.approval_asked = True
        try:
            self._watched.approve()
        except (WatchError, JsonStoreError) as error:
            self._state.trusted = False
            self._fail(_("The folder could not be approved.\n{error}"), error)
            return False
        self._view.say(Announce.FOLDER_APPROVED)
        return True

    def restrict(self) -> None:
        """Take the approval back: the CLI ignores what the project supplies again. What was
        approved of the files is kept, for a later approval."""
        if self._state is None:
            return
        self._state.trusted = False
        self._save_state()
        self._view.say(Announce.FOLDER_RESTRICTED)

    # -- inside ---------------------------------------------------------------------------

    def _offer_approval(self, workspace: Path, state: WorkspaceState) -> None:
        files = self._watched.present() if self._watched is not None else []
        if self._view.ask_approval(workspace, state.existed, files) is ApprovalChoice.APPROVE:
            self.approve()
        else:
            state.approval_asked = True  # asked once: the tab Security approves later
            self._save_state()

    def _alert(self, changes: list[FileStatus]) -> None:
        watched = self._watched
        if watched is None:
            return
        spec = ListSpec(
            title=_("A watched file changed"),
            list_label=_("Changed &files"),
            lines=[change.text() for change in changes],
            details=[self._details(watched, change) for change in changes],
            details_label=_("&Differences"),
        )
        choice = self._view.show_alert(spec)
        if choice is AlertChoice.ACCEPT:
            self._accept(watched, changes)
        elif choice is AlertChoice.RESTRICT:
            self.restrict()
        else:
            files = ", ".join(change.path for change in changes)
            self._view.say(Announce.FOLDER_CHANGED, files=files)

    def _details(self, watched: WatchedFiles, change: FileStatus) -> str:
        lines = watched.diff(change.path)
        return "\n".join(lines) if lines else _("No details are available for this file.")

    def _accept(self, watched: WatchedFiles, changes: list[FileStatus]) -> None:
        try:
            watched.approve([change.path for change in changes])
        except (WatchError, JsonStoreError) as error:
            self._fail(_("The changes could not be accepted.\n{error}"), error)

    def _fail(self, template: str, error: Exception) -> None:
        self._view.show_error(template.format(error=error))

    def _save_state(self) -> None:
        if self._state is None:
            return
        try:
            self._state.save()
        except JsonStoreError as error:
            self._fail(_("The state of the folder could not be saved.\n{error}"), error)
