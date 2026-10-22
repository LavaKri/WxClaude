"""The wx side of opening a workspace: the view of ``presenters/workspace_presenter.py``."""

from pathlib import Path

import wx

from wxclaude.i18n import _
from wxclaude.ui.feedback import Feedback


class WxWorkspaceView:
    """The folder dialog and the messages of the workspaces; ``parent`` is the window of the
    dialogs."""

    def __init__(self, parent: wx.Window, feedback: Feedback) -> None:
        self._parent = parent
        self._feedback = feedback

    def choose_folder(self, default: Path | None) -> Path | None:
        """Ask for an existing folder; the focus comes back where it was."""
        with wx.DirDialog(
            self._parent,
            _("Choose the working folder"),
            defaultPath=str(default) if default else "",
            style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST,
        ) as dialog:
            if self._feedback.modal(dialog) != wx.ID_OK:
                return None
            return Path(dialog.GetPath())

    def choose(self, title: str, prompt: str, labels: list[str]) -> int | None:
        return self._feedback.choose(title, prompt, labels)

    def show_error(self, message: str) -> None:
        self._feedback.show_error(message)

    def show_file_warning(self, details: str) -> None:
        self._feedback.show_file_warning(details)
