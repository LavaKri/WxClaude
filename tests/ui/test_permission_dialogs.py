import pytest
import wx

from wxclaude.core.claude.events import PermissionRequest
from wxclaude.core.claude.permissions import Choice
from wxclaude.ui.permission_dialog import PermissionDialog

pytestmark = pytest.mark.ui

REQUEST = PermissionRequest(
    "r", "Bash", "t", {"command": "touch x"}, "Create x", "C:\\work\\x", "Bash(touch x)"
)


@pytest.fixture
def dialog(wx_app: wx.App):
    dialog = PermissionDialog(None, REQUEST)
    yield dialog
    dialog.Destroy()
    wx.SafeYield()


def test_the_request_is_shown_and_has_the_initial_focus(dialog: PermissionDialog) -> None:
    text = dialog._request.GetValue()
    assert "Tool: Bash" in text
    assert "command: touch x" in text
    assert dialog.FindFocus() is dialog._request
    assert not dialog._request.IsEditable()


def test_the_answers(dialog: PermissionDialog) -> None:
    for identifier, choice in (
        (wx.ID_YES, Choice.ALLOW),
        (wx.ID_APPLY, Choice.ALLOW_ALWAYS),
        (wx.ID_NO, Choice.DENY),
    ):
        dialog._answer = identifier
        assert dialog.decision.choice is choice


def test_a_denial_carries_the_explanation(dialog: PermissionDialog) -> None:
    dialog._explanation.SetValue("Use the other folder")
    dialog._answer = wx.ID_NO
    assert dialog.decision.denial_message() == "Use the other folder"


def test_closing_without_answering_is_a_denial(dialog: PermissionDialog) -> None:
    assert dialog.decision.choice is Choice.DENY
    assert dialog.GetEscapeId() == wx.ID_NO


def test_always_allow_is_only_offered_with_a_rule(wx_app: wx.App) -> None:
    without = PermissionRequest("r", "Bash", "t", {}, "", "", "")
    plain = PermissionDialog(None, without)
    offered = PermissionDialog(None, REQUEST)
    try:
        assert wx.Window.FindWindowById(wx.ID_APPLY, plain) is None
        assert wx.Window.FindWindowById(wx.ID_APPLY, offered) is not None
    finally:
        plain.Destroy()
        offered.Destroy()
        wx.SafeYield()
