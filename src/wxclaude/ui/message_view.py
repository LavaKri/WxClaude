"""The wx side of the messages: the view of ``presenters/message_presenter.py``."""

from collections.abc import Callable, Sequence

import wx

from wxclaude.core.claude.plans import Plan
from wxclaude.core.claude.tasks import TaskList
from wxclaude.core.conversation.details import Link, Table
from wxclaude.core.conversation.messages import Message, ToolUse
from wxclaude.presenters.message_presenter import LinkAction, LinkChoice
from wxclaude.ui import desktop
from wxclaude.ui.details_dialogs import LinksDialog, TableDialog, ToolsDialog
from wxclaude.ui.feedback import Feedback
from wxclaude.ui.plans_dialog import PlansDialog
from wxclaude.ui.tasks_dialog import TasksDialog
from wxclaude.ui.usage_dialog import UsageDialog

_LINK_ACTIONS = {wx.ID_OPEN: LinkAction.OPEN, wx.ID_COPY: LinkAction.COPY}


class WxMessageView:
    """The dialogs of the messages, the clipboard and the browser.

    ``parent`` is the window of the dialogs; ``exchange`` gives the text of the exchange of a
    message (the conversation view knows it).
    """

    def __init__(
        self, parent: wx.Window, feedback: Feedback, exchange: Callable[[Message], str]
    ) -> None:
        self._parent = parent
        self._feedback = feedback
        self._exchange = exchange

    def exchange_of(self, message: Message) -> str:
        return self._exchange(message)

    def show_tools(self, tools: Sequence[ToolUse]) -> None:
        with ToolsDialog(self._parent, tools) as dialog:
            self._feedback.modal(dialog)

    def ask_table(self, table: Table) -> bool:
        with TableDialog(self._parent, table) as dialog:
            return bool(self._feedback.modal(dialog) == wx.ID_COPY)

    def ask_link(self, links: Sequence[Link], selected: int) -> LinkChoice | None:
        with LinksDialog(self._parent, links, selected) as dialog:
            answer = self._feedback.modal(dialog)
            index: int = dialog.selection
        action = _LINK_ACTIONS.get(answer)
        return None if action is None or index < 0 else LinkChoice(action, index)

    def show_tasks(self, tasks: TaskList) -> None:
        with TasksDialog(self._parent, tasks) as dialog:
            self._feedback.modal(dialog)

    def show_plans(self, plans: list[Plan]) -> None:
        with PlansDialog(self._parent, plans) as dialog:
            self._feedback.modal(dialog)

    def show_usage(self, lines: list[str]) -> None:
        with UsageDialog(self._parent, lines) as dialog:
            self._feedback.modal(dialog)

    def set_clipboard(self, text: str) -> bool:
        return desktop.set_clipboard(text)

    def open_url(self, url: str) -> bool:
        return desktop.launch_url(url)

    def show_error(self, message: str) -> None:
        self._feedback.show_error(message)
