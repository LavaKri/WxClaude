"""Screen reader outputs: the code that really sends a message (see ``core/screen_reader.py``)."""

import wx

from wxclaude.core import screen_reader
from wxclaude.core.announcements import MessageSink, NullMessageSink
from wxclaude.ui.uia_provider import UiaProvider

_ACTIVITY_ID = "wxclaude.announcement"


class _Announcer(wx.Window):
    """A one-pixel window, out of sight and never focused, that hosts the UI Automation provider."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent, pos=wx.Point(-5, -5), size=wx.Size(1, 1))

    def AcceptsFocus(self) -> bool:  # noqa: N802 (wx API)
        """Never takes the focus."""
        return False

    def AcceptsFocusFromKeyboard(self) -> bool:  # noqa: N802 (wx API)
        """Never reached with the Tab key."""
        return False


class UiaMessageSink:
    """Sends the messages as UI Automation notifications raised by a hidden window.

    The window is a child of the status bar. The notification makes screen readers that listen
    to it (NVDA, Narrator) say the text; the text is also the name of the window's element.
    Nothing is shown on screen and no control takes the focus. Needs Windows 10 version 1709.
    """

    def __init__(self, window: wx.Frame) -> None:
        self._announcer = _Announcer(window.GetStatusBar() or window)
        self._provider = UiaProvider(self._announcer.GetHandle())
        self._announcer.Bind(wx.EVT_WINDOW_DESTROY, self._on_announcer_destroyed)

    def show(self, text: str) -> None:
        """Raise a notification carrying ``text`` (an empty text is not worth saying)."""
        if text.strip():
            self._provider.raise_notification(text, _ACTIVITY_ID)

    def _on_announcer_destroyed(self, event: wx.WindowDestroyEvent) -> None:
        if event.GetEventObject() is self._announcer:  # not the destruction of a child
            self._provider.disconnect()
        event.Skip()

    def close(self) -> None:
        """Remove the hidden window (when another output replaces this one)."""
        self._announcer.Destroy()


def create_sink(output_id: str, window: wx.Frame) -> MessageSink:
    """The sink of the screen reader output ``output_id``; the null sink if it is not usable.

    Raises ``ScreenReaderOutputError`` if the output exists but cannot be set up.
    """
    if output_id == screen_reader.UIA.id:
        return UiaMessageSink(window)
    return NullMessageSink()
