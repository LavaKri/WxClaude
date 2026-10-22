"""What the user does with files and the desktop: export the conversation, show the workspace
folder in the file explorer, About."""

from pathlib import Path

import wx

from wxclaude import __version__
from wxclaude.core.announcements import Announce
from wxclaude.core.errors import ExportError
from wxclaude.core.export import export_text
from wxclaude.i18n import _
from wxclaude.ui import desktop
from wxclaude.ui.feedback import Feedback


class FileActions:
    """Dialogs and messages about files; ``parent`` is the window of the dialogs."""

    def __init__(self, parent: wx.Window, feedback: Feedback) -> None:
        self._parent = parent
        self._feedback = feedback

    def export(self, text: str) -> None:
        """Ask for a file and write the text of the conversation in it."""
        with wx.FileDialog(
            self._parent,
            _("Export the conversation"),
            defaultFile=_("conversation.txt"),
            wildcard=_("Text files (*.txt)|*.txt|Markdown files (*.md)|*.md"),
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dialog:
            if self._feedback.modal(dialog) != wx.ID_OK:
                return
            path = Path(dialog.GetPath())
        try:
            export_text(path, text)
        except ExportError as error:
            self._feedback.show_error(
                _("Cannot export the conversation.\n{error}").format(error=error)
            )
            return
        self._feedback.say(Announce.CONVERSATION_EXPORTED, path=path)

    def open_folder(self, folder: Path | None) -> None:
        """Show the folder of the workspace in the file explorer."""
        if folder is None:
            return
        if not folder.is_dir():
            self._feedback.show_error(
                _("The folder {folder} no longer exists.").format(folder=folder)
            )
        elif not desktop.launch_folder(folder):
            self._feedback.show_error(
                _("The folder {folder} cannot be opened in the file explorer.").format(
                    folder=folder
                )
            )

    def about(self) -> None:
        message = _("WxClaude {version}").format(version=__version__)
        self._feedback.message_box(message, _("About"), wx.ICON_INFORMATION)
