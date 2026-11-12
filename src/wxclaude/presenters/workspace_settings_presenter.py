"""The settings of a workspace: its permission rules, in the settings files of Claude Code, and
what WxClaude keeps of it, the alternative agent.

The dialog edits the rules in memory. They are loaded here, after the check of the files that the
user approved, and written once the dialog is validated.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from wxclaude.core.claude.claude_settings import ToolSettings
from wxclaude.core.config.agents import Agent
from wxclaude.core.config.settings import Settings
from wxclaude.core.errors import ClaudeSettingsError
from wxclaude.core.security.watch import ExternalChangeError
from wxclaude.i18n import _
from wxclaude.presenters.security_presenter import SecurityPresenter


@dataclass(frozen=True, slots=True)
class WorkspaceEdit:
    """What the user validated in the dialog (the rules are edited in place, in the settings
    given to the view). ``alternative_agent`` is None when the dialog has no such tab."""

    alternative_agent: Agent | None


class WorkspaceSettingsView(Protocol):
    """What the presenter asks of the interface."""

    def edit(
        self,
        tool_settings: ToolSettings,
        workspace: Path,
        alternative_agent: Agent,
        *,
        local_only: bool,
    ) -> WorkspaceEdit | None:
        """Show the dialog on ``tool_settings`` (edited in place); None if it was cancelled."""
        ...

    def show_error(self, message: str) -> None:
        """Tell the user that something failed."""
        ...


@dataclass(frozen=True, slots=True)
class WorkspaceSettingsLinks:
    """What the presenter asks of the rest of the window: the workspace, and the alternative agent
    of that workspace (to read and to change)."""

    workspace: Callable[[], Path | None]
    alternative_agent: Callable[[], Agent]
    set_alternative_agent: Callable[[Agent], None]


class WorkspaceSettingsPresenter:
    """Edits the settings of the current workspace."""

    def __init__(
        self,
        view: WorkspaceSettingsView,
        settings: Settings,
        security: SecurityPresenter,
        links: WorkspaceSettingsLinks,
    ) -> None:
        self._view = view
        self._settings = settings
        self._security = security
        self._links = links

    def edit(self) -> None:
        """Open the settings of the workspace and, once validated, write them."""
        workspace = self._links.workspace()
        if workspace is None:
            return
        self._security.check()  # a file changed since it was approved: the user decides first
        tool_settings = ToolSettings.load(workspace, guard=self._security.guard)
        edited = self._view.edit(
            tool_settings,
            workspace,
            self._links.alternative_agent(),
            local_only=self._settings.local_tools_only,
        )
        if edited is None:
            return
        if edited.alternative_agent is not None:
            self._links.set_alternative_agent(edited.alternative_agent)
        try:
            tool_settings.save()
        except ClaudeSettingsError as error:
            if isinstance(error, ExternalChangeError):
                self._security.refused(error)  # the user decides what to do with the change
            self._view.show_error(
                _("The settings could not be saved.\n{error}").format(error=error)
            )
