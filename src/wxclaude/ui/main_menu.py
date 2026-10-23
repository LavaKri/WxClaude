"""The menu bar of the main window: its tables, the recent workspaces, shortcuts and greying.

The menu knows nothing of the window: it receives what each item does (``MenuHandlers``) and is
told what is available (``refresh_enabled``).
"""

from collections.abc import Callable
from dataclasses import dataclass

import wx

from wxclaude.core.config.shortcuts import (
    FIND_COMMAND,
    FIND_NEXT_COMMAND,
    FIND_PREVIOUS_COMMAND,
    INTERRUPT_COMMAND,
    NEW_CONVERSATION_COMMAND,
    OPEN_WORKSPACE_COMMAND,
    REFRESH_CONVERSATION_COMMAND,
    RESUME_CONVERSATION_COMMAND,
    TASKS_COMMAND,
    USAGE_COMMAND,
    ConfigurableCommand,
)
from wxclaude.core.config.workspaces import workspace_label
from wxclaude.i18n import _
from wxclaude.ui.menus import SEPARATOR, MenuEntry, MenuRegistry, Needs, add_entries

Handler = Callable[[wx.CommandEvent], None]


@dataclass(frozen=True, slots=True)
class MenuHandlers:
    """What the items of the menu bar do. ``recent_workspaces`` gives the folders to list (those
    that still exist) and ``open_recent`` opens one of them."""

    open_workspace: Handler
    open_project: Handler
    export: Handler
    quit: Handler
    new_conversation: Handler
    resume_conversation: Handler
    refresh_conversation: Handler
    rename_conversation: Handler
    new_branch: Handler
    interrupt: Handler
    update_interrupt: Callable[[wx.UpdateUIEvent], None]
    choose_agent: Handler
    find: Handler
    find_next: Handler
    find_previous: Handler
    tasks: Handler
    plans: Handler
    usage: Handler
    open_workspace_folder: Handler
    workspace_settings: Handler
    preferences: Handler
    show_help: Handler
    about: Handler
    recent_workspaces: Callable[[], list[str]]
    open_recent: Callable[[str], None]


class MainMenu:
    """Builds the menu bar of ``window`` and keeps the items whose state changes."""

    def __init__(self, window: wx.Frame, handlers: MenuHandlers) -> None:
        self._window = window
        self._handlers = handlers
        self._recent_ids: dict[int, str] = {}
        registry = MenuRegistry()
        self.command_items = registry.command_items
        self.needs_workspace = registry.needs_workspace
        self.needs_conversation = registry.needs_conversation

        self._file_menu = wx.Menu()
        add_entries(window, self._file_menu, self._file_entries(), registry)
        self._recent_menu = wx.Menu()
        self.recent_item = self._file_menu.AppendSubMenu(self._recent_menu, _("&Recent"))
        quit_entry = MenuEntry(_("&Quit\tCtrl+Q"), handlers.quit, item_id=wx.ID_EXIT)
        add_entries(window, self._file_menu, [quit_entry], registry)

        conversation_menu = wx.Menu()
        kept = add_entries(window, conversation_menu, self._conversation_entries(), registry)
        self.interrupt_item = kept["interrupt"]
        window.Bind(wx.EVT_UPDATE_UI, handlers.update_interrupt, self.interrupt_item)
        search_menu = wx.Menu()
        add_entries(window, search_menu, self._search_entries(), registry)
        conversation_menu.AppendSubMenu(search_menu, _("Sear&ch"))

        tools_menu = wx.Menu()
        kept_tools = add_entries(window, tools_menu, self._tools_entries(), registry)
        self.usage_item = kept_tools["usage"]
        help_menu = wx.Menu()
        help_entry = MenuEntry(_("WxClaude &help\tF1"), handlers.show_help)
        about = MenuEntry(_("&About"), handlers.about, item_id=wx.ID_ABOUT)
        add_entries(window, help_menu, [help_entry, about], registry)

        menu_bar = wx.MenuBar()
        menu_bar.Append(self._file_menu, _("&File"))
        menu_bar.Append(conversation_menu, _("&Conversation"))
        menu_bar.Append(tools_menu, _("&Tools"))
        menu_bar.Append(help_menu, _("&Help"))
        window.SetMenuBar(menu_bar)
        window.Bind(wx.EVT_MENU_OPEN, self._on_menu_open)

    # A conversation belongs to a workspace: without a workspace only the items that open one are
    # available, and without a conversation those that need one are greyed.

    def _file_entries(self) -> list[MenuEntry | None]:
        h = self._handlers
        return [
            MenuEntry(_("&Open workspace…"), h.open_workspace, OPEN_WORKSPACE_COMMAND),
            MenuEntry(_("Open from Claude &projects…"), h.open_project),
            MenuEntry(_("&Export the conversation…"), h.export, needs=Needs.CONVERSATION),
            SEPARATOR,
        ]

    def _conversation_entries(self) -> list[MenuEntry | None]:
        h = self._handlers
        workspace, conversation = Needs.WORKSPACE, Needs.CONVERSATION
        return [
            MenuEntry(
                _("&New conversation"), h.new_conversation, NEW_CONVERSATION_COMMAND, workspace
            ),
            MenuEntry(
                _("&Resume a conversation…"),
                h.resume_conversation,
                RESUME_CONVERSATION_COMMAND,
                workspace,
            ),
            MenuEntry(
                _("Re&fresh the conversation"),
                h.refresh_conversation,
                REFRESH_CONVERSATION_COMMAND,
                conversation,
            ),
            MenuEntry(_("Ren&ame the conversation"), h.rename_conversation, needs=conversation),
            MenuEntry(_("New conversation &branch"), h.new_branch, needs=conversation),
            # Greyed until deleting is built (a later milestone).
            MenuEntry(_("&Delete the conversation"), enabled=False),
            MenuEntry(_("&Interrupt Claude"), h.interrupt, INTERRUPT_COMMAND, key="interrupt"),
            MenuEntry(_("&Modify the agent…"), h.choose_agent, needs=conversation),
        ]

    def _search_entries(self) -> list[MenuEntry | None]:
        h = self._handlers
        conversation = Needs.CONVERSATION
        return [
            MenuEntry(_("&Find…"), h.find, FIND_COMMAND, conversation),
            MenuEntry(_("Find &next"), h.find_next, FIND_NEXT_COMMAND, conversation),
            MenuEntry(_("Find &previous"), h.find_previous, FIND_PREVIOUS_COMMAND, conversation),
        ]

    def _tools_entries(self) -> list[MenuEntry | None]:
        h = self._handlers
        return [
            MenuEntry(_("Task &list…"), h.tasks, TASKS_COMMAND, Needs.CONVERSATION),
            MenuEntry(_("Pla&n…"), h.plans, needs=Needs.CONVERSATION),
            MenuEntry(_("Claude &usage…"), h.usage, USAGE_COMMAND, key="usage"),
            MenuEntry(
                _("Open the workspace &folder"), h.open_workspace_folder, needs=Needs.WORKSPACE
            ),
            MenuEntry(_("Workspace &settings…"), h.workspace_settings, needs=Needs.WORKSPACE),
            MenuEntry(_("&Preferences…"), h.preferences),
        ]

    # What changes --------------------------------------------------------------------------------

    def apply_shortcuts(self, shortcut_for: Callable[[ConfigurableCommand], str]) -> None:
        """Show (and activate) the shortcut of each configurable command in its menu item."""
        for command, item, text in self.command_items:
            shortcut = shortcut_for(command)
            item.SetItemLabel(f"{text}\t{shortcut}" if shortcut else text)

    def refresh_enabled(
        self, *, has_workspace: bool, has_conversation: bool, busy: bool, refreshing: bool
    ) -> None:
        """Grey out what needs a workspace or a conversation that is not there, and the usage
        while the gauges are read (what it would show is not known yet)."""
        for item in self.needs_workspace:
            item.Enable(has_workspace)
        for item in self.needs_conversation:
            item.Enable(has_conversation)
        self.interrupt_item.Enable(busy)
        self.usage_item.Enable(not refreshing)

    def refresh_recent(self) -> None:
        """Rebuild the recent workspaces (the handler drops the folders that no longer exist)."""
        for item in list(self._recent_menu.GetMenuItems()):
            self._recent_menu.Delete(item)
        self._recent_ids.clear()
        for folder in self._handlers.recent_workspaces():
            item = self._recent_menu.Append(wx.ID_ANY, workspace_label(folder).replace("&", "&&"))
            self._recent_ids[item.GetId()] = folder
            self._window.Bind(wx.EVT_MENU, self._on_recent, item)
        self.recent_item.Enable(bool(self._recent_ids))

    def _on_recent(self, event: wx.CommandEvent) -> None:
        folder = self._recent_ids.get(event.GetId())
        if folder is not None:
            self._handlers.open_recent(folder)

    def _on_menu_open(self, event: wx.MenuEvent) -> None:
        if event.GetMenu() is self._file_menu:
            self.refresh_recent()
        event.Skip()
