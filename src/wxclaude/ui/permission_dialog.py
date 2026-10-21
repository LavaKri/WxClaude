"""The question Claude asks before it runs a tool: allow, always allow, or deny and explain."""

import wx

from wxclaude.core.events import PermissionRequest
from wxclaude.core.permissions import Choice, Decision, describe_request
from wxclaude.i18n import _

_ALWAYS_ID = wx.ID_APPLY


class PermissionDialog(wx.Dialog):
    """Shows what Claude wants to do. Esc and closing the window mean *Deny*.

    The initial focus is on the description of the request, so a screen reader reads it first and a
    stray Enter does nothing; the buttons are one Tab away.
    """

    def __init__(self, parent: wx.Window, request: PermissionRequest) -> None:
        super().__init__(parent, title=_("Claude asks for permission"))
        self._answer = wx.ID_NO
        # Each label is created right before its control so that screen readers pair them.
        request_label = wx.StaticText(self, label=_("&Request"))
        self._request = wx.TextCtrl(
            self,
            value=describe_request(request),
            style=wx.TE_MULTILINE | wx.TE_READONLY,
            name=_("Request"),
        )
        self._request.SetMinSize(
            wx.Size(self._request.GetCharWidth() * 70, self._request.GetCharHeight() * 8)
        )
        explanation_label = wx.StaticText(self, label=_("&Explanation for Claude, if you deny"))
        self._explanation = wx.TextCtrl(self, style=wx.TE_MULTILINE, name=_("Explanation"))
        self._explanation.SetMinSize(wx.Size(-1, self._explanation.GetCharHeight() * 3 + 10))

        buttons = wx.BoxSizer(wx.HORIZONTAL)
        allow = wx.Button(self, wx.ID_YES, _("&Allow"))
        buttons.Add(allow, 0, wx.RIGHT, 6)
        if request.suggested_rule:
            always = wx.Button(self, _ALWAYS_ID, _("Always allow &this"))
            buttons.Add(always, 0, wx.RIGHT, 6)
        buttons.Add(wx.Button(self, wx.ID_NO, _("&Deny")), 0)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(request_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        sizer.Add(self._request, 1, wx.EXPAND | wx.ALL, 8)
        sizer.Add(explanation_label, 0, wx.LEFT | wx.RIGHT, 8)
        sizer.Add(self._explanation, 0, wx.EXPAND | wx.ALL, 8)
        sizer.Add(buttons, 0, wx.ALL, 8)
        self.SetSizerAndFit(sizer)
        allow.SetDefault()
        self.SetEscapeId(wx.ID_NO)
        self.Bind(wx.EVT_BUTTON, self._on_button)
        self._request.SetFocus()

    def _on_button(self, event: wx.CommandEvent) -> None:
        identifier = event.GetId()
        if identifier in (wx.ID_YES, wx.ID_NO, _ALWAYS_ID):
            self._answer = identifier
            self.EndModal(identifier)
        else:
            event.Skip()

    @property
    def decision(self) -> Decision:
        """What the user decided (a closed dialog is a denial)."""
        if self._answer == wx.ID_YES:
            return Decision(Choice.ALLOW)
        if self._answer == _ALWAYS_ID:
            return Decision(Choice.ALLOW_ALWAYS)
        return Decision(Choice.DENY, str(self._explanation.GetValue()))
