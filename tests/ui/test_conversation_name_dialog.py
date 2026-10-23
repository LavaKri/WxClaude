from collections.abc import Iterator

import pytest
import wx

from wxclaude.ui.conversation_name_dialog import ConversationNameDialog

pytestmark = pytest.mark.ui


@pytest.fixture
def dialog(wx_app: wx.App) -> Iterator[ConversationNameDialog]:
    dialog = ConversationNameDialog(None, "New conversation", "Conversation 3")
    yield dialog
    dialog.Destroy()
    wx.SafeYield()  # a dialog is deleted when the application is idle


def test_the_proposed_name_is_shown_and_selected(dialog: ConversationNameDialog) -> None:
    assert dialog.name == "Conversation 3"
    assert dialog._name.GetStringSelection() == "Conversation 3"


def test_the_name_loses_the_spaces_around_it(dialog: ConversationNameDialog) -> None:
    dialog._name.SetValue("  Notes  ")
    assert dialog.name == "Notes"
