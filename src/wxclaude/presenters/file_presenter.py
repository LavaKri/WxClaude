"""What the user does with files and the desktop: export the conversation, show the workspace
folder in the file explorer, the help page, About."""

from pathlib import Path
from typing import Protocol

from wxclaude import __version__
from wxclaude.core.conversation.export import export_text
from wxclaude.core.errors import ExportError, HelpError
from wxclaude.core.help import help_page
from wxclaude.i18n import _


class FileView(Protocol):
    """What the presenter asks of the interface for the files and the desktop."""

    def ask_export_path(self) -> Path | None:
        """Ask where to export the conversation; None if cancelled."""
        ...

    def open_folder(self, folder: Path) -> bool:
        """Show ``folder`` in the file explorer; False if the desktop refused."""
        ...

    def open_file(self, path: Path) -> bool:
        """Open ``path`` with its application (the browser for HTML); False if refused."""
        ...

    def show_about(self, message: str) -> None:
        """The About message."""
        ...

    def show_error(self, message: str) -> None:
        """Tell the user that something failed."""
        ...


class FilePresenter:
    """Exports, opens folders and pages, and says what failed."""

    def __init__(self, view: FileView) -> None:
        self._view = view

    def export(self, text: str) -> None:
        """Ask for a file and write the text of the conversation in it."""
        path = self._view.ask_export_path()
        if path is None:
            return
        try:
            export_text(path, text)
        except ExportError as error:
            self._view.show_error(_("Cannot export the conversation.\n{error}").format(error=error))

    def open_folder(self, folder: Path | None) -> None:
        """Show the folder of the workspace in the file explorer."""
        if folder is None:
            return
        if not folder.is_dir():
            self._view.show_error(_("The folder {folder} no longer exists.").format(folder=folder))
        elif not self._view.open_folder(folder):
            self._view.show_error(
                _("The folder {folder} cannot be opened in the file explorer.").format(
                    folder=folder
                )
            )

    def show_help(self, language: str) -> None:
        """Open the help page of ``language`` in the browser."""
        try:
            page = help_page(language)
        except HelpError as error:
            self._view.show_error(_("The help page cannot be opened.\n{error}").format(error=error))
            return
        if not self._view.open_file(page):
            self._view.show_error(
                _("The help page {page} cannot be opened in the browser.").format(page=page)
            )

    def about(self) -> None:
        self._view.show_about(_("WxClaude {version}").format(version=__version__))
