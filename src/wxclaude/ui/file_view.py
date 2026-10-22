"""The wx side of the files and the desktop: the view of ``presenters/file_presenter.py``."""

from pathlib import Path

import wx

from wxclaude.i18n import _
from wxclaude.ui import desktop
from wxclaude.ui.feedback import Feedback


class WxFileView:
    """The export dialog, the file explorer, the browser and the messages; ``parent`` is the
    window of the dialogs."""

    def __init__(self, parent: wx.Window, feedback: Feedback) -> None:
        self._parent = parent
        self._feedback = feedback

    def ask_export_path(self) -> Path | None:
        with wx.FileDialog(
            self._parent,
            _("Export the conversation"),
            defaultFile=_("conversation.txt"),
            wildcard=_("Text files (*.txt)|*.txt|Markdown files (*.md)|*.md"),
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dialog:
            if self._feedback.modal(dialog) != wx.ID_OK:
                return None
            return Path(dialog.GetPath())

    def open_folder(self, folder: Path) -> bool:
        return desktop.launch_folder(folder)

    def open_file(self, path: Path) -> bool:
        return desktop.launch_file(path)

    def show_about(self, message: str) -> None:
        self._feedback.message_box(message, _("About"), wx.ICON_INFORMATION)

    def show_error(self, message: str) -> None:
        self._feedback.show_error(message)
