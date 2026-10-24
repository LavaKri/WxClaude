from collections.abc import Iterator

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
def dialog(wx_app: wx.App) -> Iterator[PermissionDialog]:
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


def test_the_waiting_time_is_the_first_line_of_the_request(wx_app: wx.App) -> None:
    dialog = PermissionDialog(
        None, REQUEST, "Without an answer by 13:59 (10 min), Claude denies it."
    )
    lines = dialog._request.GetValue().split("\n")
    assert lines[0] == "Without an answer by 13:59 (10 min), Claude denies it."
    assert lines[1] == "Tool: Bash"
    dialog.Destroy()
    wx.SafeYield()


def test_without_a_waiting_time_the_request_starts_with_the_tool(dialog: PermissionDialog) -> None:
    assert dialog._request.GetValue().startswith("Tool: Bash")


def test_a_plan_has_its_own_title_and_shows_its_text(wx_app: wx.App) -> None:
    plan = PermissionRequest("p", "ExitPlanMode", "t", {"plan": "# Plan\n\nStep one"}, "", "", "")
    dialog = PermissionDialog(None, plan)
    try:
        assert dialog.GetTitle() == "Claude proposes a plan"
        text = dialog._request.GetValue()
        assert text.endswith("# Plan\n\nStep one")
        assert "Tool:" not in text
        assert dialog.FindFocus() is dialog._request
    finally:
        dialog.Destroy()
        wx.SafeYield()


def test_an_ordinary_request_keeps_the_ordinary_title(dialog: PermissionDialog) -> None:
    assert dialog.GetTitle() == "Claude asks for permission"
