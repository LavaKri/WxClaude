"""What can be done with the messages: their details (tools, table, links), copying them, the task
list and the plans of the conversation and the usage of Claude (see
``docs/conversation-display.md``)."""

import enum
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from wxclaude.core.claude.claude_files import ClaudeFiles
from wxclaude.core.claude.plans import Plan
from wxclaude.core.claude.tasks import TaskList
from wxclaude.core.claude.usage import UsageTracker
from wxclaude.core.conversation.details import DetailAction, Link, Table, message_details
from wxclaude.core.conversation.messages import Message, ToolUse
from wxclaude.core.errors import PlanReadError, TaskReadError
from wxclaude.i18n import _


class LinkAction(enum.Enum):
    """What the user asked for a link."""

    OPEN = "open"
    COPY = "copy"


@dataclass(frozen=True, slots=True)
class LinkChoice:
    """The link chosen in the list (its index) and what to do with it."""

    action: LinkAction
    index: int


class MessageView(Protocol):
    """What the presenter asks of the interface for the messages and their details."""

    def exchange_of(self, message: Message) -> str:
        """The text of the exchange (prompt and answers) ``message`` belongs to."""
        ...

    def show_tools(self, tools: Sequence[ToolUse]) -> None:
        """The tools used by an answer."""
        ...

    def ask_table(self, table: Table) -> bool:
        """Show the rows of a table; True if the user asked to copy it."""
        ...

    def ask_link(self, links: Sequence[Link], selected: int) -> LinkChoice | None:
        """Show the links (``selected`` first selected); None if the user only closed the list."""
        ...

    def show_tasks(self, tasks: TaskList) -> None:
        """The task list of the conversation."""
        ...

    def show_plans(self, plans: list[Plan]) -> None:
        """The plans of the conversation."""
        ...

    def show_usage(self, lines: list[str]) -> None:
        """The usage of Claude, one fact per line."""
        ...

    def set_clipboard(self, text: str) -> bool:
        """Put ``text`` on the clipboard; False if the clipboard cannot be used."""
        ...

    def open_url(self, url: str) -> bool:
        """Hand a web or mail address to the system; False if it refused."""
        ...

    def show_error(self, message: str) -> None:
        """Tell the user that something failed."""
        ...


class MessagePresenter:
    """Shows the details of the messages and does what the user asks (copy, open a link).

    ``conversation_id`` gives the current conversation and ``usage`` what is known of the usage
    of Claude.
    """

    def __init__(
        self,
        view: MessageView,
        conversation_id: Callable[[], str],
        usage: UsageTracker,
        files: ClaudeFiles,
    ) -> None:
        self._view = view
        self._files = files
        self._conversation_id = conversation_id
        self._usage = usage

    def show_tasks(self) -> None:
        """The tasks Claude wrote for this conversation (read from its task folder)."""
        try:
            tasks = self._files.load_tasks(self._conversation_id())
        except TaskReadError as error:
            self._view.show_error(_("Cannot read the tasks.\n{error}").format(error=error))
            return
        self._view.show_tasks(tasks)

    def show_plans(self) -> None:
        """The plans Claude wrote in this conversation (named by its session file)."""
        try:
            plans = self._files.load_plans(self._conversation_id())
        except PlanReadError as error:
            self._view.show_error(_("Cannot read the plans.\n{error}").format(error=error))
            return
        self._view.show_plans(plans)

    def show_usage(self) -> None:
        """The gauges of the subscription and the tokens spent, as far as the answers told."""
        self._view.show_usage(self._usage.lines(datetime.now()))

    def act(self, action: DetailAction, message: Message, line: int) -> None:
        """An item of the context menu of the conversation view."""
        if action is DetailAction.COPY_MESSAGE:
            self._copy(message.text)
        elif action is DetailAction.COPY_EXCHANGE:
            self._copy(self._view.exchange_of(message))
        else:
            self._show_details(action, message, line)

    def _show_details(self, action: DetailAction, message: Message, line: int) -> None:
        """The tools, the table or the links of ``message``."""
        details = message_details(message)
        if action is DetailAction.TOOLS:
            self._view.show_tools(details.tools)
        elif action is DetailAction.TABLE:
            table = details.table_at(line)
            if table is not None and self._view.ask_table(table):
                self._copy(table.source)
        elif action is DetailAction.LINKS and details.links:
            choice = self._view.ask_link(details.links, details.link_index_at(line))
            if choice is None:
                return
            link = details.links[choice.index]
            if choice.action is LinkAction.OPEN:
                self._open_link(link)
            else:
                self._copy(link.url)

    def _open_link(self, link: Link) -> None:
        """Open a web or mail address in the default application; any other kind is refused."""
        if not link.can_open:
            self._view.show_error(
                _("This kind of address is not opened from here: {url}").format(url=link.url)
            )
        elif not self._view.open_url(link.url):
            self._view.show_error(_("The address {url} cannot be opened.").format(url=link.url))

    def _copy(self, text: str) -> None:
        if not self._view.set_clipboard(text):
            self._view.show_error(_("The clipboard cannot be used."))
