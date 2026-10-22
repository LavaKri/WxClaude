"""Opening a workspace: from a folder, from the Claude projects, from the recent list, at startup.

The presenter keeps the current workspace and what is remembered about it. What follows from a
new workspace (closing the conversation, selecting another one, the title and the greyed items) is
done by the window, through ``WorkspaceLinks``; what is asked or shown goes through
``WorkspaceView``.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from wxclaude.core.claude_projects import list_projects
from wxclaude.core.settings import Settings
from wxclaude.core.workspace_state import WorkspaceState
from wxclaude.core.workspaces import add_recent, remove_missing, workspace_label
from wxclaude.i18n import _


class WorkspaceView(Protocol):
    """What the presenter asks of the interface to open a workspace."""

    def choose_folder(self, default: Path | None) -> Path | None:
        """Ask for an existing folder (``default`` proposed); None if cancelled."""
        ...

    def choose(self, title: str, prompt: str, labels: list[str]) -> int | None:
        """Ask the user to pick one of ``labels``; its index, None if cancelled."""
        ...

    def show_error(self, message: str) -> None:
        """Tell the user that something failed."""
        ...

    def show_file_warning(self, details: str) -> None:
        """Tell the user that a file of the application was damaged (and what was done)."""
        ...


@dataclass(frozen=True, slots=True)
class WorkspaceLinks:
    """What the presenter asks of the window: close the conversation, select the one of a
    workspace, refresh what depends on the workspace (title, greyed items), save the settings."""

    close_conversation: Callable[[], None]
    select_conversation: Callable[[Path], None]
    changed: Callable[[], None]
    save_settings: Callable[[], None]


class WorkspacePresenter:
    """The current workspace and the ways to open another one."""

    def __init__(self, view: WorkspaceView, settings: Settings, links: WorkspaceLinks) -> None:
        self._view = view
        self._settings = settings
        self._links = links
        self.workspace: Path | None = None
        self.state: WorkspaceState | None = None  # what is remembered about the workspace

    def open(self, folder: Path) -> None:
        """Make ``folder`` the working folder; the conversation of another folder is closed."""
        changed = folder != self.workspace
        if changed:
            self._links.close_conversation()
        self._set(folder)
        if changed:
            self._links.select_conversation(folder)

    def _set(self, folder: Path) -> None:
        """Make ``folder`` the working folder and remember it in the recent list."""
        if self.state is None or folder != self.workspace:
            self.state = WorkspaceState.load(folder, self._settings.workspaces_dir)
            if self.state.warning:
                self._view.show_file_warning(self.state.warning)
        self.workspace = folder
        self._settings.last_workspace = str(folder)
        self._settings.recent_workspaces = add_recent(self._settings.recent_workspaces, folder)
        self._links.changed()
        self._links.save_settings()

    def choose_folder(self) -> None:
        """Ask for a folder and open it."""
        folder = self._view.choose_folder(self.workspace)
        if folder is not None:
            self.open(folder)

    def choose_project(self) -> None:
        """Open one of the folders Claude Code has already worked in."""
        projects = list_projects()
        if not projects:
            self._view.show_error(_("Claude Code has no project yet."))
            return
        labels = [workspace_label(str(project.folder)) for project in projects]
        index = self._view.choose(_("Open from Claude projects"), _("Choose a project:"), labels)
        if index is not None:
            self.open(projects[index].folder)

    def open_recent(self, folder: str) -> None:
        """Open a recent workspace; a folder that is gone is dropped from the list."""
        if Path(folder).is_dir():
            self.open(Path(folder))
            return
        self._settings.recent_workspaces = remove_missing(self._settings.recent_workspaces)
        self._view.show_error(
            _("The folder {folder} no longer exists. It was removed from the recent list.").format(
                folder=folder
            )
        )

    def recent(self) -> list[str]:
        """The recent workspaces whose folder still exists (the others are dropped)."""
        self._settings.recent_workspaces = remove_missing(self._settings.recent_workspaces)
        return list(self._settings.recent_workspaces)

    def restore_last_session(self) -> None:
        """At startup: open the last workspace and select its conversation.

        Without the option, at the first start, or if that workspace no longer exists, there is
        no workspace and no conversation: only what opens a workspace is available.
        """
        settings = self._settings
        if not (settings.reopen_last and settings.last_workspace):
            return
        folder = Path(settings.last_workspace)
        if not folder.is_dir():
            return
        self._set(folder)
        self._links.select_conversation(folder)
