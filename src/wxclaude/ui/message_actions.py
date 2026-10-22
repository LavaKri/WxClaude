"""What can be done with the messages: their details (tools, table, links), copying them, the task
list and the plans of the conversation and the usage of Claude (see
``docs/conversation-display.md``)."""

from collections.abc import Callable
from datetime import datetime

import wx

from wxclaude.core.details import DetailAction, Link, message_details
from wxclaude.core.errors import PlanReadError, TaskReadError
from wxclaude.core.messages import Message
from wxclaude.core.plans import load_plans
from wxclaude.core.tasks import load_tasks
from wxclaude.core.usage import UsageTracker
from wxclaude.i18n import _
from wxclaude.ui import desktop
from wxclaude.ui.details_dialogs import LinksDialog, TableDialog, ToolsDialog
from wxclaude.ui.plans_dialog import PlansDialog
from wxclaude.ui.tasks_dialog import TasksDialog
from wxclaude.ui.usage_dialog import UsageDialog


class MessageActions:
    """Opens the dialogs about the messages and does what they ask (copy, open a link).

    ``parent`` is the window of the dialogs, ``show_modal`` shows one and returns its result,
    ``show_error`` reports a failure; ``conversation_id`` gives the current
    conversation, ``usage`` what is known of the usage of Claude and ``exchange_of`` the text of
    the exchange (prompt and answers) a message belongs to.
    """

    def __init__(
        self,
        parent: wx.Window,
        show_modal: Callable[[wx.Dialog], int],
        show_error: Callable[[str], None],
        conversation_id: Callable[[], str],
        usage: UsageTracker,
        exchange_of: Callable[[Message], str],
    ) -> None:
        self._parent = parent
        self._show_modal = show_modal
        self._show_error = show_error
        self._conversation_id = conversation_id
        self._usage = usage
        self._exchange_of = exchange_of

    def show_tasks(self) -> None:
        """The tasks Claude wrote for this conversation (read from its task folder)."""
        try:
            tasks = load_tasks(self._conversation_id())
        except TaskReadError as error:
            self._show_error(_("Cannot read the tasks.\n{error}").format(error=error))
            return
        with TasksDialog(self._parent, tasks) as dialog:
            self._show_modal(dialog)

    def show_plans(self) -> None:
        """The plans Claude wrote in this conversation (named by its session file)."""
        try:
            plans = load_plans(self._conversation_id())
        except PlanReadError as error:
            self._show_error(_("Cannot read the plans.\n{error}").format(error=error))
            return
        with PlansDialog(self._parent, plans) as dialog:
            self._show_modal(dialog)

    def show_usage(self) -> None:
        """The gauges of the subscription and the tokens spent, as far as the answers told."""
        with UsageDialog(self._parent, self._usage.lines(datetime.now())) as dialog:
            self._show_modal(dialog)

    def act(self, action: DetailAction, message: Message, line: int) -> None:
        """An item of the context menu of the conversation view."""
        if action is DetailAction.COPY_MESSAGE:
            self._copy(message.text)
        elif action is DetailAction.COPY_EXCHANGE:
            self._copy(self._exchange_of(message))
        else:
            self._show_details(action, message, line)

    def _show_details(self, action: DetailAction, message: Message, line: int) -> None:
        """The dialog of the tools, the table or the links of ``message``."""
        details = message_details(message)
        if action is DetailAction.TOOLS:
            with ToolsDialog(self._parent, details.tools) as tools_dialog:
                self._show_modal(tools_dialog)
        elif action is DetailAction.TABLE:
            table = details.table_at(line)
            if table is None:
                return
            with TableDialog(self._parent, table) as table_dialog:
                if self._show_modal(table_dialog) == wx.ID_COPY:
                    self._copy(table.source)
        elif action is DetailAction.LINKS and details.links:
            selected = details.link_index_at(line)
            with LinksDialog(self._parent, details.links, selected) as links_dialog:
                answer = self._show_modal(links_dialog)
                index = links_dialog.selection
            if index < 0:
                return
            if answer == wx.ID_OPEN:
                self._open_link(details.links[index])
            elif answer == wx.ID_COPY:
                self._copy(details.links[index].url)

    def _open_link(self, link: Link) -> None:
        """Open a web or mail address in the default application; any other kind is refused."""
        if not link.can_open:
            self._show_error(
                _("This kind of address is not opened from here: {url}").format(url=link.url)
            )
        elif not desktop.launch_url(link.url):
            self._show_error(_("The address {url} cannot be opened.").format(url=link.url))

    def _copy(self, text: str) -> None:
        if not desktop.set_clipboard(text):
            self._show_error(_("The clipboard cannot be used."))
