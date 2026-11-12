"""The history of the announcements, in a read-only text field (Help menu)."""

import wx

from wxclaude.i18n import _
from wxclaude.ui.feedback import Feedback
from wxclaude.ui.text_dialog import TextDialog


def show_history(parent: wx.Window, feedback: Feedback) -> None:
    """Show the announcements of this session, the most recent last, the caret on that one."""
    lines = feedback.announcements.history.lines() or [_("No announcement yet.")]
    with TextDialog(
        parent, _("Announcement history"), _("&Announcements"), lines, caret_at_end=True
    ) as dialog:
        feedback.modal(dialog)
