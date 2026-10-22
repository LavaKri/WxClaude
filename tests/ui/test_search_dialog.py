import pytest
import wx

from wxclaude.core.conversation.search import SearchOptions
from wxclaude.ui.search_dialog import SearchDialog

pytestmark = pytest.mark.ui


def test_the_previous_search_is_proposed_and_selected(wx_app: wx.App) -> None:
    previous = SearchOptions("needle", match_case=True, whole_word=True)
    dialog = SearchDialog(None, previous)
    try:
        assert dialog.options == previous
        assert dialog._term.GetStringSelection() == "needle"  # typing replaces it
    finally:
        dialog.Destroy()
        wx.SafeYield()


def test_the_options_follow_the_controls(wx_app: wx.App) -> None:
    dialog = SearchDialog(None)
    try:
        assert dialog.options == SearchOptions("")
        dialog._term.SetValue("abc")
        dialog._match_case.SetValue(True)
        assert dialog.options == SearchOptions("abc", match_case=True)
        dialog._whole_word.SetValue(True)
        assert dialog.options.whole_word
    finally:
        dialog.Destroy()
        wx.SafeYield()
