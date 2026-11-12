"""What the user chooses to see of the conversation: the system messages, the line under the
answers that sums up the tools, and the marks of bold and italic.

Each choice lives in the settings, in the conversation view and, for two of them, in a check item
of the menu. They are put together here, so that a new choice is added in one place.
"""

from collections.abc import Callable

from wxclaude.core.config.settings import Settings
from wxclaude.ui.conversation_view import ConversationView
from wxclaude.ui.main_menu import MainMenu


class DisplayOptions:
    """Shows the conversation as the settings say, and changes a choice from the menu."""

    def __init__(
        self,
        conversation: ConversationView,
        menu: MainMenu,
        settings: Settings,
        save: Callable[[], None],
    ) -> None:
        self._conversation = conversation
        self._menu = menu
        self._settings = settings
        self._save = save

    def apply(self) -> None:
        """Show the conversation and the check items of the menu as the settings say (at the
        start, and after the Preferences, which can change the system messages). What is already
        as the settings say is left alone: the view is not rebuilt for it."""
        settings = self._settings
        self._conversation.set_show_hidden(not settings.hide_system_messages)
        self._conversation.set_show_tools_summary(settings.show_tools_summary)
        self._menu.tools_summary_item.Check(settings.show_tools_summary)
        self._conversation.set_without_marks(settings.remove_markdown_marks)
        self._menu.marks_item.Check(settings.remove_markdown_marks)

    def set_tools_summary(self, show: bool) -> None:
        """The item of the Conversation menu: show or hide the line under the answers."""
        self._settings.show_tools_summary = show
        self._conversation.set_show_tools_summary(show)
        self._save()

    def set_without_marks(self, without: bool) -> None:
        """The item of the Display menu: remove or show the marks of bold and italic."""
        self._settings.remove_markdown_marks = without
        self._conversation.set_without_marks(without)
        self._save()
