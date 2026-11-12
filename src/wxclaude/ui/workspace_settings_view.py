"""The wx side of the settings of a workspace: the view of
``presenters/workspace_settings_presenter.py``."""

from pathlib import Path

import wx

from wxclaude.core.claude.claude_settings import ToolSettings
from wxclaude.core.config.agents import Agent
from wxclaude.core.config.providers import ProviderStore
from wxclaude.presenters.security_presenter import SecurityPresenter
from wxclaude.presenters.workspace_settings_presenter import WorkspaceEdit
from wxclaude.ui.feedback import Feedback
from wxclaude.ui.workspace_settings_dialog import WorkspaceSettingsDialog


class WxWorkspaceSettingsView:
    """The dialog of the workspace settings and the messages; ``parent`` is the window of the
    dialog. The trust of the folder and the providers are what the tabs of the dialog work on."""

    def __init__(
        self,
        parent: wx.Window,
        feedback: Feedback,
        security: SecurityPresenter,
        providers: ProviderStore,
    ) -> None:
        self._parent = parent
        self._feedback = feedback
        self._security = security
        self._providers = providers

    def edit(
        self,
        tool_settings: ToolSettings,
        workspace: Path,
        alternative_agent: Agent,
        *,
        local_only: bool,
    ) -> WorkspaceEdit | None:
        with WorkspaceSettingsDialog(
            self._parent,
            tool_settings,
            local_only=local_only,
            security=self._security,
            workspace=workspace,
            alternative_agent=alternative_agent,
            providers=self._providers,
        ) as dialog:
            if self._feedback.modal(dialog) != wx.ID_OK:
                return None
            return WorkspaceEdit(dialog.alternative_agent)

    def show_error(self, message: str) -> None:
        self._feedback.show_error(message)
