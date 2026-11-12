"""The prompt area of the main window: its label, the field, the three buttons and the keys that
send.

The controls are children of the panel of the window (not of a panel of their own), so the label
stays right before its field for the screen readers and the Tab order is the one of the window.
What sending does belongs to the window, which gives it here as ``PromptActions``.
"""

from collections.abc import Callable
from dataclasses import dataclass

import wx

from wxclaude.core.config.shortcuts import (
    AGENT_COMMAND,
    SEND_ALTERNATIVE_COMMAND,
    SEND_COMMAND,
    ConfigurableCommand,
)
from wxclaude.i18n import _
from wxclaude.ui.prompt_field import PromptField
from wxclaude.ui.shortcut_keys import shortcut_from_event


@dataclass(frozen=True, slots=True)
class PromptActions:
    """What the window does for the prompt area: send (with the alternative agent or not),
    interrupt, choose the agent, and whether sending or interrupting is possible now."""

    send: Callable[[bool], None]
    interrupt: Callable[[], None]
    choose_agent: Callable[[], None]
    can_send: Callable[[], bool]
    can_interrupt: Callable[[], bool]


class PromptArea:
    """The field and the buttons that send what is typed in it."""

    def __init__(
        self,
        parent: wx.Window,
        actions: PromptActions,
        shortcut_for: Callable[[ConfigurableCommand], str],
    ) -> None:
        self._actions = actions
        self._shortcut_for = shortcut_for
        self.label = wx.StaticText(parent, label=_("&Prompt"))
        self.field = PromptField(
            parent,
            on_agent=actions.choose_agent,
            agent_shortcut=lambda: shortcut_for(AGENT_COMMAND),
        )
        self.field.Bind(wx.EVT_KEY_DOWN, self._on_key)

        self._send = wx.Button(parent)  # the labels come from the shortcuts, see apply_shortcuts
        self._alternative = wx.Button(parent)
        self._interrupt = wx.Button(parent, label=_("&Interrupt Claude"))
        self._send.Bind(wx.EVT_BUTTON, lambda _event: actions.send(False))
        self._alternative.Bind(wx.EVT_BUTTON, lambda _event: actions.send(True))
        self._interrupt.Bind(wx.EVT_BUTTON, lambda _event: actions.interrupt())
        for button in (self._send, self._alternative):
            button.Bind(wx.EVT_UPDATE_UI, lambda event: event.Enable(actions.can_send()))
        self._interrupt.Bind(wx.EVT_UPDATE_UI, lambda event: event.Enable(actions.can_interrupt()))

        self._buttons = wx.BoxSizer(wx.HORIZONTAL)
        self._buttons.Add(self._send, 0, wx.RIGHT, 6)
        self._buttons.Add(self._alternative, 0, wx.RIGHT, 6)
        self._buttons.Add(self._interrupt, 0)

    def add_to(self, sizer: wx.BoxSizer) -> None:
        """Lay the label, the field and the buttons out, in this order, at the end of ``sizer``."""
        sizer.Add(self.label, 0, wx.LEFT, 6)
        sizer.Add(self.field, 1, wx.EXPAND | wx.ALL, 6)
        sizer.Add(self._buttons, 0, wx.ALL, 6)

    @property
    def send_label(self) -> str:
        """The label of the button *Send*."""
        return str(self._send.GetLabel())

    @property
    def alternative_label(self) -> str:
        """The label of the button *Send with the alternative agent*."""
        return str(self._alternative.GetLabel())

    def apply_shortcuts(self) -> None:
        """Show the shortcuts in the labels of the send buttons."""
        self._send.SetLabel(self._label(SEND_COMMAND))
        self._alternative.SetLabel(self._label(SEND_ALTERNATIVE_COMMAND))

    def _label(self, command: ConfigurableCommand) -> str:
        """Label of a send button: its action, then its shortcut (the screen reader says it)."""
        shortcut = self._shortcut_for(command)
        if command is SEND_COMMAND:
            return _("&Send ({shortcut})").format(shortcut=shortcut) if shortcut else _("&Send")
        if shortcut:
            return _("Send with the &alternative agent ({shortcut})").format(shortcut=shortcut)
        return _("Send with the &alternative agent")

    def _on_key(self, event: wx.KeyEvent) -> None:
        shortcut = shortcut_from_event(event)
        if shortcut:
            if shortcut == self._shortcut_for(SEND_COMMAND):
                self._actions.send(False)
                return
            if shortcut == self._shortcut_for(SEND_ALTERNATIVE_COMMAND):
                self._actions.send(True)
                return
        event.Skip()  # a plain Enter adds a line break
