"""The wx side of the usage gauge and the statistics (``presenters/usage_presenter.py``)."""

from collections.abc import Callable

import wx

from wxclaude.i18n import _
from wxclaude.ui.feedback import Feedback
from wxclaude.ui.text_dialog import TextDialog
from wxclaude.ui.worker import run_in_background


class WxUsageView:
    """The two read-only dialogs, shown through ``feedback`` so that the focus comes back."""

    def __init__(self, parent: wx.Window, feedback: Feedback) -> None:
        self._parent = parent
        self._feedback = feedback

    def show_gauges(self, lines: list[str]) -> None:
        with TextDialog(self._parent, _("Usage gauge"), _("&Usage"), lines) as dialog:
            self._feedback.modal(dialog)

    def show_statistics(self, lines: list[str]) -> None:
        with TextDialog(self._parent, _("Statistics"), _("&Statistics"), lines) as dialog:
            self._feedback.modal(dialog)

    def fetch_balances(
        self, task: Callable[[], list[str]], on_done: Callable[[list[str]], None]
    ) -> None:
        run_in_background(
            task,
            on_done,
            lambda message: on_done([message]),
            name="provider-balances",
            alive=lambda: bool(self._parent),  # False once the window is gone
        )
