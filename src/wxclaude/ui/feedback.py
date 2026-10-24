"""What the main window tells the user: the status bar, the announcements and the dialogs.

Every dialog of the application is shown through ``Feedback.modal``, which puts the focus back
where it was when the dialog closes (rule A of ``docs/focus.md``).
"""

from collections.abc import Callable
from pathlib import Path

import wx

from wxclaude.core.claude.session_reader import Session, read_session
from wxclaude.core.errors import ScreenReaderOutputError, SessionReadError
from wxclaude.core.labels import shorten
from wxclaude.core.speech.announcements import (
    Announce,
    AnnouncementCenter,
    Category,
    Destination,
    NullMessageSink,
    SoundPlayer,
)
from wxclaude.core.speech.sounds import WinsoundPlayer
from wxclaude.i18n import _
from wxclaude.ui.message_sinks import create_sink

_POSITION_FIELD = 0
_STEP_FIELD = 1
_MESSAGE_FIELD = 2
STATUS_TEXT_LIMIT = 200  # characters: a longer text is cut, a screen reader reads a field in one go


def create_sound_player() -> SoundPlayer:
    """The player of the announcement sounds (the tests replace it by a silent one)."""
    return WinsoundPlayer()


class Feedback:
    """Says things to the user through ``frame``: its status bar, the screen reader, dialogs.

    ``is_closing`` tells whether the window is closing (the focus is then left alone).
    """

    def __init__(
        self,
        frame: wx.Frame,
        is_closing: Callable[[], bool],
        destination_of: Callable[[Category], Destination],
    ) -> None:
        self._frame = frame
        self._is_closing = is_closing
        self._output_id: str | None = None  # the screen reader output in use
        self.announcements = AnnouncementCenter(
            destination_of=destination_of,
            on_error=self._on_screen_reader_error,
            sound_player=create_sound_player(),
            show_dialog=lambda text: self.show_info(text),
        )

    # Status bar and announcements --------------------------------------------------------------

    def say(self, announce: Announce, **values: object) -> None:
        """Say an announcement where its category says; a text is also shown in the status bar
        (a sound or "no announcement" leaves the status bar alone, a screen reader may read it)."""
        text = self.announcements.notify(announce, **values)
        if text is not None:
            self.set_status(text)

    def set_status(self, text: str) -> None:
        """The message field of the status bar (the last one)."""
        self._set_field(text, _MESSAGE_FIELD)

    def show_step(self, text: str) -> None:
        """Second field of the status bar: the step Claude works on, empty when there is none."""
        self._set_field(text, _STEP_FIELD)

    def show_position(self, number: int, total: int) -> None:
        """First field of the status bar: the prompt the caret is in, 'Message 3 of 8'."""
        text = _("Message {number} of {total}").format(number=number, total=total) if total else ""
        self._set_field(text, _POSITION_FIELD)

    def _set_field(self, text: str, field: int) -> None:
        self._frame.SetStatusText(shorten(text, STATUS_TEXT_LIMIT), field)

    def apply_screen_reader_output(self, output_id: str) -> None:
        """Connect the announcements to the output chosen in the Preferences."""
        if output_id == self._output_id:
            return
        self._output_id = output_id
        try:
            sink = create_sink(output_id, self._frame)
        except ScreenReaderOutputError as error:
            sink = NullMessageSink()
            self._on_screen_reader_error(error)
        self.announcements.message_sink.close()
        self.announcements.message_sink = sink

    def _on_screen_reader_error(self, error: ScreenReaderOutputError) -> None:
        self.show_error(_("The screen reader output cannot be used.\n{error}").format(error=error))

    # Dialogs ----------------------------------------------------------------------------------

    def modal(self, dialog: wx.Dialog) -> int:
        """Show ``dialog``; when it closes the focus is back where it was (docs/focus.md)."""
        focused = wx.Window.FindFocus()
        try:
            return int(dialog.ShowModal())
        finally:
            wx.CallAfter(self._restore_focus, focused)  # once the dialog is destroyed

    def _restore_focus(self, focused: wx.Window | None) -> None:
        """Put the focus back on ``focused`` unless it was deliberately moved inside the window."""
        frame = self._frame
        if self._is_closing() or not frame or not focused:
            return
        current = wx.Window.FindFocus()
        if current is None or not frame.IsDescendant(current):
            focused.SetFocus()

    def message_box(self, message: str, caption: str, icon: int) -> None:
        """A message with an OK button; the focus comes back where it was."""
        with wx.MessageDialog(self._frame, message, caption, wx.OK | icon) as dialog:
            self.modal(dialog)

    def show_error(self, message: str) -> None:
        self.message_box(message, _("Error"), wx.ICON_ERROR)

    def confirm(self, title: str, message: str) -> bool:
        """Ask a Yes / No question, No by default; True for Yes."""
        style = wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION
        with wx.MessageDialog(self._frame, message, title, style) as dialog:
            return bool(self.modal(dialog) == wx.ID_YES)

    def show_info(self, message: str) -> None:
        self.message_box(message, _("Information"), wx.ICON_INFORMATION)

    def choose(self, title: str, prompt: str, labels: list[str]) -> int | None:
        """Ask the user to pick one of ``labels``; its index, None if cancelled."""
        with wx.SingleChoiceDialog(self._frame, prompt, title, labels) as dialog:
            if self.modal(dialog) != wx.ID_OK:
                return None
            return int(dialog.GetSelection())

    def read_session(self, path: Path) -> Session | None:
        """The session in ``path``; None (with the error shown) if it cannot be read."""
        try:
            return read_session(path)
        except SessionReadError as error:
            self.show_error(_("Cannot read the conversation.\n{error}").format(error=error))
            return None

    def show_file_warning(self, details: str) -> None:
        """Tell the user that a file of the application was damaged (and what was done)."""
        self.message_box(
            _("A configuration file could not be read.\n{details}").format(details=details),
            _("Warning"),
            wx.ICON_WARNING,
        )
