"""Dialog showing the plans of the current conversation."""

import wx

from wxclaude.core.claude.plans import Plan
from wxclaude.core.list_spec import ListSpec
from wxclaude.i18n import _
from wxclaude.ui.list_dialog import ListDialog


class PlansDialog(ListDialog):
    """The plans of Claude, one per line (the name of the file), and the text of the selected
    one; the last plan is selected at the start."""

    def __init__(self, parent: wx.Window, plans: list[Plan]) -> None:
        lines = [plan.line for plan in plans]
        texts = [plan.text for plan in plans]
        if not lines:
            lines, texts = [_("No plan in this conversation yet.")], [""]
        super().__init__(
            parent,
            ListSpec(
                _("Plan"),
                list_label=_("&Plans"),
                lines=lines,
                details=texts,
                details_label=_("&Text of the plan"),
                selection=len(lines) - 1,
            ),
        )
