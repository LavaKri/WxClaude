import pytest
import wx

from wxclaude.core.claude.tasks import Task, TaskList
from wxclaude.core.conversation.details import DetailAction, Link, message_details
from wxclaude.core.conversation.messages import Message, Role, ToolUse
from wxclaude.ui.conversation_view import ConversationView
from wxclaude.ui.details_dialogs import LinksDialog, TableDialog, ToolsDialog
from wxclaude.ui.tasks_dialog import TasksDialog
from wxclaude.ui.usage_dialog import UsageDialog

pytestmark = pytest.mark.ui

TABLE_ANSWER = "Result:\n\n| Name | Size |\n|---|---|\n| a.txt | 3 |\n\nSee [docs](https://a.test)."


@pytest.fixture
def frame(wx_app: wx.App):
    frame = wx.Frame(None)
    yield frame
    frame.Destroy()
    wx.SafeYield()


def _close(dialog: wx.Dialog) -> None:
    dialog.Destroy()
    wx.SafeYield()


def test_the_tools_dialog_lists_the_tools_and_details_the_selected_one(frame: wx.Frame) -> None:
    tools = [
        ToolUse("1", "Read", {"file_path": "a.py"}, "contents"),
        ToolUse("2", "Bash", {"command": "ls"}, "boom", is_error=True),
    ]
    dialog = ToolsDialog(frame, tools)
    assert dialog._list.GetStrings() == ["Read, a.py", "Bash, ls, failed"]
    assert dialog.selection == 0
    assert dialog.details_text.startswith("Tool: Read\nfile_path: a.py")
    dialog._list.SetSelection(1)
    dialog._on_select(wx.CommandEvent())
    assert "The tool failed." in dialog.details_text
    assert dialog.FindFocus() is dialog._list
    _close(dialog)


def test_the_table_dialog_reads_one_row_per_line(frame: wx.Frame) -> None:
    (table,) = message_details(Message("a", Role.ASSISTANT, TABLE_ANSWER)).tables
    dialog = TableDialog(frame, table)
    assert dialog._list.GetStrings() == ["Name: a.txt, Size: 3"]
    assert dialog.FindWindowById(wx.ID_COPY) is not None
    _close(dialog)


def test_the_links_dialog_selects_the_requested_link(frame: wx.Frame) -> None:
    links = [Link("one", "https://1.test", 0), Link("two", "https://2.test", 3)]
    dialog = LinksDialog(frame, links, selected=1)
    assert dialog._list.GetStrings() == ["one, https://1.test", "two, https://2.test"]
    assert dialog.selection == 1
    assert dialog.FindWindowById(wx.ID_OPEN) is not None
    assert dialog.FindWindowById(wx.ID_COPY) is not None
    _close(dialog)


def test_an_action_button_ends_the_dialog_with_its_identifier(frame: wx.Frame) -> None:
    dialog = LinksDialog(frame, [Link("one", "https://1.test", 0)])
    ended: list[int] = []
    dialog.EndModal = ended.append  # type: ignore[method-assign]
    wx.PostEvent(dialog, wx.CommandEvent(wx.wxEVT_BUTTON, wx.ID_COPY))
    wx.SafeYield()
    assert ended == [wx.ID_COPY]
    _close(dialog)


def test_the_task_dialog_lists_the_tasks_with_their_description(frame: wx.Frame) -> None:
    tasks = TaskList(
        [
            Task("1", "Prepare", "Get ready", "completed"),
            Task("2", "Build", "Compile", "pending", ("1",)),
        ],
        ["3.json"],
    )
    dialog = TasksDialog(frame, tasks)
    assert dialog._list.GetStrings() == [
        "1, Prepare, completed",
        "2, Build, pending",
        "Unreadable task files: 3.json",
    ]
    assert dialog.details_text == "Get ready"
    _close(dialog)


def test_the_task_dialog_says_when_there_is_no_task(frame: wx.Frame) -> None:
    dialog = TasksDialog(frame, TaskList())
    assert dialog._list.GetStrings() == ["No task in this conversation yet."]
    _close(dialog)


def test_the_usage_dialog_shows_the_report_and_has_the_focus_on_it(frame: wx.Frame) -> None:
    dialog = UsageDialog(frame, ["first fact.", "second fact."])
    assert dialog.report == "first fact.\nsecond fact."
    assert dialog.FindFocus() is dialog._report
    _close(dialog)


# The context menu of the conversation view ---------------------------------------------------


class _Actions:
    def __init__(self) -> None:
        self.calls: list[tuple[DetailAction, Message, int]] = []

    def __call__(self, action: DetailAction, message: Message, line: int) -> None:
        self.calls.append((action, message, line))


@pytest.fixture
def actions() -> _Actions:
    return _Actions()


@pytest.fixture
def view(frame: wx.Frame, actions: _Actions) -> ConversationView:
    view = ConversationView(frame, lambda *_a, **_k: None, actions)
    view.set_messages(
        [
            Message("1", Role.USER, "Hello"),
            Message(
                "2",
                Role.ASSISTANT,
                TABLE_ANSWER,
                model="m",
                tools=[ToolUse("t", "Read", {"file_path": "a.py"})],
            ),
        ]
    )
    return view


def _open_menu(
    view: ConversationView, monkeypatch: pytest.MonkeyPatch, choose: int | None = None
) -> list[str]:
    """Open the context menu as the Applications key does, without showing it.

    Returns the labels of its items; ``choose`` is the index of the item the user picks.
    """
    labels: list[str] = []

    def popup(menu: wx.Menu, _position: wx.Point) -> bool:
        items = menu.GetMenuItems()
        labels.extend(item.GetItemLabel() for item in items)
        if choose is not None:
            menu.ProcessEvent(wx.CommandEvent(wx.wxEVT_MENU, items[choose].GetId()))
        return True

    monkeypatch.setattr(view, "PopupMenu", popup)
    event = wx.ContextMenuEvent(wx.wxEVT_CONTEXT_MENU, view.GetId(), wx.DefaultPosition)
    view._on_context_menu(event)
    return labels


def _caret_on(view: ConversationView, needle: str) -> None:
    view.SetInsertionPoint(view.text.index(needle))


def test_the_menu_offers_what_the_message_holds(
    view: ConversationView, monkeypatch: pytest.MonkeyPatch
) -> None:
    _caret_on(view, "| a.txt")
    assert _open_menu(view, monkeypatch) == [
        "Show the &tools used…",
        "Show the t&able…",
        "Show the &links…",
        "&Copy the message",
        "Copy the &exchange",
        "&Next heading	T",
        "&Previous heading	Shift+T",
    ]


def test_the_menu_jumps_to_the_next_and_the_previous_heading(
    view: ConversationView, monkeypatch: pytest.MonkeyPatch
) -> None:
    view.SetInsertionPoint(0)
    labels = _open_menu(view, monkeypatch, choose=2)  # copy, copy, then "Next heading"
    wx.SafeYield()
    assert labels[2] == "&Next heading	T"
    assert view.GetInsertionPoint() == view.text.index("## Answer")
    _open_menu(view, monkeypatch, choose=-1)  # "Previous heading", the last item
    wx.SafeYield()
    assert view.GetInsertionPoint() == 0


def test_the_table_is_only_offered_on_its_lines(
    view: ConversationView, monkeypatch: pytest.MonkeyPatch
) -> None:
    _caret_on(view, "Result:")
    assert "Show the t&able…" not in _open_menu(view, monkeypatch)


def test_a_prompt_only_offers_to_be_copied(
    view: ConversationView, monkeypatch: pytest.MonkeyPatch
) -> None:
    view.SetInsertionPoint(0)
    assert _open_menu(view, monkeypatch)[:2] == ["&Copy the message", "Copy the &exchange"]


def test_choosing_an_item_hands_the_message_and_the_line_over(
    view: ConversationView, actions: _Actions, monkeypatch: pytest.MonkeyPatch
) -> None:
    _caret_on(view, "| a.txt")
    _open_menu(view, monkeypatch, choose=1)  # the table
    wx.SafeYield()
    ((action, message, line),) = actions.calls
    assert action is DetailAction.TABLE
    assert message.id == "2"
    assert line == 4  # "Result:", blank, header, separator, then the row


def test_without_a_message_at_the_caret_no_menu_opens_not_even_the_native_one(
    frame: wx.Frame, actions: _Actions, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = ConversationView(frame, lambda *_a, **_k: None, actions)
    popups: list[object] = []
    monkeypatch.setattr(empty, "PopupMenu", lambda *args: popups.append(args))
    skipped: list[bool] = []
    event = wx.ContextMenuEvent(wx.wxEVT_CONTEXT_MENU, empty.GetId(), wx.DefaultPosition)
    event.Skip = lambda *_a: skipped.append(True)  # type: ignore[method-assign]
    empty._on_context_menu(event)
    assert skipped == []  # skipping would let the field show its own menu
    assert popups == []


def _key(view: ConversationView, kind: int, code: int, *, shift: bool = False) -> list[bool]:
    """Send a key event to the view; return [True] if it was passed on to the native field."""
    event = wx.KeyEvent(kind)
    event.SetEventObject(view)
    event.SetKeyCode(code)
    event.SetShiftDown(shift)
    skipped: list[bool] = []
    event.Skip = lambda *_a: skipped.append(True)  # type: ignore[method-assign]
    view.GetEventHandler().ProcessEvent(event)
    return skipped


def test_shift_f10_opens_our_menu_and_the_native_field_never_sees_the_key(
    view: ConversationView, monkeypatch: pytest.MonkeyPatch
) -> None:
    _caret_on(view, "Result:")
    labels: list[list[str]] = []
    monkeypatch.setattr(
        view, "PopupMenu", lambda menu, _pos: labels.append(_menu_labels(menu)) or True
    )
    assert _key(view, wx.wxEVT_KEY_DOWN, wx.WXK_F10, shift=True) == []
    assert labels[0][-4:-2] == ["&Copy the message", "Copy the &exchange"]
    assert _key(view, wx.wxEVT_KEY_UP, wx.WXK_F10, shift=True) == []  # no native menu on key up
    assert _key(view, wx.wxEVT_KEY_UP, wx.WXK_WINDOWS_MENU) == []
    assert _key(view, wx.wxEVT_KEY_UP, ord("A")) == [True]  # other keys are left alone
    assert _key(view, wx.wxEVT_KEY_DOWN, wx.WXK_F10) == [True]  # F10 alone is not a menu key


def _menu_labels(menu: wx.Menu) -> list[str]:
    return [item.GetItemLabel() for item in menu.GetMenuItems()]


def test_adopting_details_keeps_the_text_and_gives_the_tools(view: ConversationView) -> None:
    before = view.GetValue()
    caret = 5
    view.SetInsertionPoint(caret)
    fresh = [
        Message("1", Role.USER, "Hello"),
        Message("2", Role.ASSISTANT, TABLE_ANSWER, model="m", tools=[ToolUse("t", "Bash", {})]),
    ]
    view.adopt_details(fresh)
    assert view.GetValue() == before
    assert view.GetInsertionPoint() == caret
    assert view.document.spans[1].message.tools[0].name == "Bash"
    view.adopt_details([Message("9", Role.USER, "Other text")])  # another text: left alone
    assert view.document.spans[1].message.tools[0].name == "Bash"
