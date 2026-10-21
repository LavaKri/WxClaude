"""Menus described as tables: each entry gives its text, action, shortcut and what it needs.

``add_entries`` appends the entries to a menu, binds them, and records the items that need a
workspace or a conversation and those whose shortcut is configurable.
"""

import enum
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import wx

from wxclaude.core.shortcuts import ConfigurableCommand


class Needs(enum.Enum):
    """What an item needs to be available."""

    NOTHING = "nothing"
    WORKSPACE = "workspace"
    CONVERSATION = "conversation"


@dataclass(frozen=True, slots=True)
class MenuEntry:
    """One item of a menu. ``key`` names the items the caller needs to keep."""

    text: str
    handler: Callable[[wx.CommandEvent], None] | None = None
    command: ConfigurableCommand | None = None
    needs: Needs = Needs.NOTHING
    item_id: int = wx.ID_ANY
    enabled: bool = True
    key: str = ""


#: An entry that is a separator line.
SEPARATOR = None


@dataclass(slots=True)
class MenuRegistry:
    """The items created, by what they need, and the items of configurable commands."""

    command_items: list[tuple[ConfigurableCommand, wx.MenuItem, str]] = field(default_factory=list)
    needs_workspace: list[wx.MenuItem] = field(default_factory=list)
    needs_conversation: list[wx.MenuItem] = field(default_factory=list)


def add_entries(
    window: wx.Window,
    menu: wx.Menu,
    entries: Sequence[MenuEntry | None],
    registry: MenuRegistry,
) -> dict[str, wx.MenuItem]:
    """Append ``entries`` to ``menu`` and bind them on ``window``; return the items with a key."""
    kept: dict[str, wx.MenuItem] = {}
    for entry in entries:
        if entry is None:
            menu.AppendSeparator()
            continue
        item = menu.Append(entry.item_id, entry.text)
        if entry.handler is not None:
            window.Bind(wx.EVT_MENU, entry.handler, item)
        if not entry.enabled:
            item.Enable(False)
        if entry.command is not None:
            registry.command_items.append((entry.command, item, entry.text))
        if entry.needs is Needs.WORKSPACE:
            registry.needs_workspace.append(item)
        elif entry.needs is Needs.CONVERSATION:
            registry.needs_conversation.append(item)
        if entry.key:
            kept[entry.key] = item
    return kept
