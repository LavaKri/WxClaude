"""Gives the focus back to the control it was on when the user comes back to the window.

Alt+Tab away and back: the window does not always put the focus back where it was. The rule is in
``docs/focus.md`` (rule E): the control that has the focus is remembered when the window loses the
foreground, and it gets the focus again when the window comes back, once. A control that cannot
take it again (a button, which the user did not choose to come back to, or a control that is
greyed or hidden by now, such as *Interrupt Claude* once the answer ended) is replaced by the
default control of the window.
"""

from collections.abc import Callable

import wx


class FocusKeeper:
    """Remembers the focused control of ``frame`` when it is deactivated and gives the focus back
    when it is activated again. ``default`` gives the control to use when the remembered one cannot
    take the focus (None: none). Nothing is done while the window closes."""

    def __init__(
        self,
        frame: wx.Frame,
        is_closing: Callable[[], bool],
        default: Callable[[], wx.Window | None],
    ) -> None:
        self._frame = frame
        self._is_closing = is_closing
        self._default = default
        self._remembered: wx.Window | None = None
        frame.Bind(wx.EVT_ACTIVATE, self._on_activate)

    def _on_activate(self, event: wx.ActivateEvent) -> None:
        event.Skip()
        if self._is_closing():
            return
        if not event.GetActive():
            self._remembered = self._focused_control()
        else:
            remembered, self._remembered = self._remembered, None  # used once, never kept
            if remembered is not None:
                wx.CallAfter(self._restore, remembered)

    def _focused_control(self) -> wx.Window | None:
        """The control of the window that has the focus. None when the window is blocked by a
        dialog (it is not Alt+Tab: the dialog gives the focus back, rule A) or when the focus is
        not in the window."""
        if not self._frame.IsEnabled():
            return None
        focused = wx.Window.FindFocus()
        return focused if focused is not None and self._frame.IsDescendant(focused) else None

    def _restore(self, remembered: wx.Window) -> None:
        if self._is_closing() or not self._frame.IsEnabled():
            return
        target = remembered if _can_take_focus(remembered) else self._default()
        if target is not None and wx.Window.FindFocus() is not target:
            target.SetFocus()


def _can_take_focus(control: wx.Window) -> bool:
    """Can the user be taken back to ``control``? Not a button, not a control that is gone,
    greyed or hidden."""
    return (
        bool(control)
        and not isinstance(control, wx.Button)
        and control.IsEnabled()
        and (control.IsShownOnScreen())
    )
