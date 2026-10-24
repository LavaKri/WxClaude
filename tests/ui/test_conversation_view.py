from collections.abc import Callable, Iterator

import pytest
import wx

from wxclaude.core.conversation.headings import to_utf16
from wxclaude.core.conversation.messages import Message, Role, ToolUse
from wxclaude.core.speech.announcements import Announce
from wxclaude.ui.conversation_view import ConversationView

pytestmark = pytest.mark.ui


class _Said:
    def __init__(self) -> None:
        self.calls: list[tuple[Announce, dict[str, object]]] = []

    def __call__(self, announce: Announce, **values: object) -> None:
        self.calls.append((announce, values))


def _last(said: _Said) -> Announce:
    return said.calls[-1][0]


@pytest.fixture
def said() -> _Said:
    return _Said()


@pytest.fixture
def view(wx_app: wx.App, said: _Said) -> Iterator[ConversationView]:
    frame = wx.Frame(None)
    view = ConversationView(frame, said)
    view.set_messages(
        [
            Message("1", Role.USER, "Hello"),
            Message("2", Role.ASSISTANT, "## Part\nbody", model="m"),
            Message("3", Role.USER, "Again 😀"),
        ]
    )
    yield view
    frame.Destroy()
    wx.SafeYield()


def _press(view: ConversationView, key: str, *, shift: bool = False) -> None:
    event = wx.KeyEvent(wx.wxEVT_KEY_DOWN)
    event.SetEventObject(view)
    event.SetKeyCode(ord(key))
    event.SetShiftDown(shift)
    view.GetEventHandler().ProcessEvent(event)


def test_h_goes_to_the_next_heading_and_says_its_line(view: ConversationView, said: _Said) -> None:
    _press(view, "H")
    assert view.GetInsertionPoint() == len("# You say: Hello\nHello\n\n")
    assert said.calls[-1] == (
        Announce.MOVED_HEADING,
        {"title": "Answer from m", "level": 2, "line": "Answer from m"},
    )


def test_digit_goes_to_the_next_heading_of_that_level(view: ConversationView, said: _Said) -> None:
    _press(view, "1")
    assert said.calls[-1][1]["title"] == "You say: Again 😀"
    _press(view, "2", shift=True)
    assert said.calls[-1] == (
        Announce.MOVED_HEADING,
        {"title": "Part", "level": 2, "line": "Part"},
    )


def test_shift_goes_backwards_and_the_end_is_announced(view: ConversationView, said: _Said) -> None:
    _press(view, "H", shift=True)
    assert _last(said) is Announce.NO_PREVIOUS_HEADING
    _press(view, "3")
    assert said.calls[-1] == (Announce.NO_NEXT_HEADING_OF_LEVEL, {"level": 3})


BLOCKS = (
    "Intro\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n- one\n  - nested\n  - deeper\n- two\n\n"
    "1. first\n2. second\n\n| C |\n|---|\n| 3 |"
)


@pytest.fixture
def blocks(view: ConversationView) -> ConversationView:
    view.set_messages([Message("1", Role.ASSISTANT, BLOCKS, model="m")])
    return view


def _line_at_caret(view: ConversationView) -> str:
    text = view.document.text
    start = view.GetInsertionPoint()
    return text[start : text.index("\n", start)]


def test_t_goes_from_table_to_table(blocks: ConversationView, said: _Said) -> None:
    _press(blocks, "T")
    assert _line_at_caret(blocks) == "| A | B |"
    assert said.calls[-1] == (
        Announce.MOVED_TABLE,
        {"columns": "2 columns", "rows": "1 row", "line": "| A | B |"},
    )
    _press(blocks, "T")
    assert _line_at_caret(blocks) == "| C |"
    _press(blocks, "T")
    assert _last(said) is Announce.NO_NEXT_TABLE
    _press(blocks, "T", shift=True)
    assert _line_at_caret(blocks) == "| A | B |"
    _press(blocks, "T", shift=True)
    assert _last(said) is Announce.NO_PREVIOUS_TABLE


def test_l_goes_from_list_to_list_without_the_nested_ones(
    blocks: ConversationView, said: _Said
) -> None:
    _press(blocks, "L")
    assert _line_at_caret(blocks) == "- one"
    assert said.calls[-1] == (Announce.MOVED_LIST, {"items": "2 items", "line": "- one"})
    _press(blocks, "L")
    assert _line_at_caret(blocks) == "1. first"
    _press(blocks, "L")
    assert _last(said) is Announce.NO_NEXT_LIST
    _press(blocks, "L", shift=True)
    assert _line_at_caret(blocks) == "- one"
    _press(blocks, "L", shift=True)
    assert _last(said) is Announce.NO_PREVIOUS_LIST


def _move_to_line(view: ConversationView, line: str) -> None:
    view.SetInsertionPoint(view.document.text.index(line))


def test_i_stays_among_the_items_of_the_list_the_caret_is_in(
    blocks: ConversationView, said: _Said
) -> None:
    _move_to_line(blocks, "- one")
    _press(blocks, "I")
    assert _line_at_caret(blocks) == "- two"  # the nested item is skipped
    assert said.calls[-1] == (Announce.MOVED, {"line": "- two"})
    _press(blocks, "I")
    assert _last(said) is Announce.NO_NEXT_ITEM  # the other list is not entered
    _press(blocks, "I", shift=True)
    assert _line_at_caret(blocks) == "- one"
    _press(blocks, "I", shift=True)
    assert _last(said) is Announce.NO_PREVIOUS_ITEM


def test_i_in_a_nested_list_moves_among_the_nested_items(blocks: ConversationView) -> None:
    _move_to_line(blocks, "  - nested")
    _press(blocks, "I")
    assert _line_at_caret(blocks) == "  - deeper"


def test_i_outside_a_list_says_there_is_no_item(blocks: ConversationView, said: _Said) -> None:
    _move_to_line(blocks, "Intro")
    _press(blocks, "I")
    assert _last(said) is Announce.NO_NEXT_ITEM


def test_positions_after_an_emoji_use_utf16_units(view: ConversationView, said: _Said) -> None:
    view.SetInsertionPoint(view.GetLastPosition())
    _press(view, "H", shift=True)
    assert said.calls[-1][1]["title"] == "You say: Again 😀"
    text = view.document.text
    assert view.GetInsertionPoint() == len(text[: text.index("# You say: Again")])


def test_appending_keeps_the_caret(view: ConversationView) -> None:
    view.SetInsertionPoint(3)
    view.append_message(Message("4", Role.ASSISTANT, "More", model="m"))
    assert view.GetInsertionPoint() == 3
    assert view.GetValue() == view.document.text


def test_the_message_under_the_caret_is_found(view: ConversationView) -> None:
    view.SetInsertionPoint(0)
    span = view.message_at_caret()
    assert span is not None
    assert span.message.id == "1"


def test_system_messages_can_be_shown_and_hidden_again(view: ConversationView) -> None:
    view.append_message(Message("5", Role.USER, "continue", hidden=True))
    assert "continue" not in view.GetValue()
    view.SetInsertionPoint(view.document.spans[1].start)  # in the answer
    view.set_show_hidden(True)
    assert "# You say: continue" in view.GetValue()
    assert view.message_at_caret().message.id == "2"  # type: ignore[union-attr]
    view.set_show_hidden(False)
    assert "continue" not in view.GetValue()
    assert view.message_at_caret().message.id == "2"  # type: ignore[union-attr]


def test_the_view_knows_whether_it_shows_given_messages(view: ConversationView) -> None:
    messages = [
        Message("1", Role.USER, "Hello"),
        Message("2", Role.ASSISTANT, "## Part\nbody", model="m"),
        Message("3", Role.USER, "Again 😀"),
    ]
    assert view.shows(messages)
    assert not view.shows([*messages, Message("4", Role.USER, "More")])
    messages[1] = Message("2", Role.ASSISTANT, "changed", model="m")
    assert not view.shows(messages)


def test_the_focus_goes_to_the_start_of_the_last_prompt(view: ConversationView) -> None:
    view.SetInsertionPoint(0)
    view.focus_last_prompt()
    assert view.HasFocus()
    text = view.document.text
    assert view.GetInsertionPoint() == text.index("# You say: Again")
    view.set_messages([Message("1", Role.ASSISTANT, "only an answer", model="m")])
    view.focus_last_prompt()
    assert view.GetInsertionPoint() == 0  # no prompt: the start


def test_the_position_in_the_prompts_is_reported_when_the_caret_moves(
    destroy_after: Callable[[wx.Frame], wx.Frame],
) -> None:
    frame = destroy_after(wx.Frame(None))
    reported: list[tuple[int, int]] = []
    view = ConversationView(
        frame, lambda *_a, **_k: None, None, lambda n, t: reported.append((n, t))
    )
    view.set_messages(
        [
            Message("1", Role.USER, "One"),
            Message("2", Role.ASSISTANT, "Answer", model="m"),
            Message("3", Role.USER, "Two"),
        ]
    )
    assert reported[-1] == (1, 2)
    view.SetInsertionPoint(view.GetLastPosition())
    view.report_position()
    assert reported[-1] == (2, 2)
    view.report_position()
    assert reported.count((2, 2)) == 1  # not repeated while it does not change
    view.append_message(Message("4", Role.USER, "Three"))
    assert reported[-1] == (3, 3)  # the caret, at the old end, now starts the new prompt
    view.clear_messages()
    assert reported[-1] == (0, 0)


def _with_tools() -> list[Message]:
    return [
        Message("1", Role.USER, "Hello"),
        Message("2", Role.ASSISTANT, "First answer", model="m", tools=[ToolUse("t", "Read", {})]),
        Message("3", Role.USER, "Again"),
        Message("4", Role.ASSISTANT, "Second answer", model="m", tools=[ToolUse("u", "Bash", {})]),
    ]


def test_the_line_under_the_answers_can_be_shown_and_hidden_again(
    view: ConversationView,
) -> None:
    view.set_messages(_with_tools())
    assert "tool" not in view.GetValue()
    view.set_show_tools_summary(True)
    assert view.GetValue().count("1 file read") == 1
    assert view.GetValue().count("1 command run") == 1
    view.set_show_tools_summary(False)
    assert "1 file read" not in view.GetValue()


def test_showing_the_line_keeps_the_caret_on_its_message_at_the_same_place(
    view: ConversationView,
) -> None:
    view.set_messages(_with_tools())
    view.SetInsertionPoint(view.text.index("Again") + 2)
    view.set_show_tools_summary(True)
    assert view.GetInsertionPoint() == view.text.index("Again") + 2
    view.SetInsertionPoint(view.text.index("irst answer"))  # in an answer that gains a line
    view.set_show_tools_summary(False)
    assert view.GetInsertionPoint() == view.text.index("irst answer")
    view.set_show_tools_summary(True)
    assert view.GetInsertionPoint() == view.text.index("irst answer")


def test_a_caret_at_the_end_stays_at_the_end_when_the_text_grows(view: ConversationView) -> None:
    view.set_messages(_with_tools())
    view.SetInsertionPoint(view.GetLastPosition())
    view.set_show_tools_summary(True)
    assert view.GetInsertionPoint() == view.GetLastPosition()


def test_the_view_knows_the_line_when_it_compares_the_messages(view: ConversationView) -> None:
    messages = _with_tools()
    view.set_messages(messages)
    assert view.shows(messages)
    view.set_show_tools_summary(True)
    assert view.shows(messages)
    bare = [Message(m.id, m.role, m.text, model=m.model) for m in messages]
    assert not view.shows(bare)  # without the tools there is no line: another text


def test_the_caret_stays_on_the_prompt_when_the_file_gives_other_identifiers(
    view: ConversationView,
) -> None:
    view.append_message(Message("local-1", Role.USER, "Sent now"))
    view.focus_last_prompt()
    before = view.GetInsertionPoint()
    assert before > 0
    # After the answer the view is rebuilt from the session file: same messages, the identifiers of
    # the CLI, and the tools of the answer, which the live messages did not have.
    from_file = [
        Message("u1", Role.USER, "Hello"),
        Message("u2", Role.ASSISTANT, "## Part\nbody", model="m", tools=[ToolUse("t", "Read", {})]),
        Message("u3", Role.USER, "Again 😀"),
        Message("u4", Role.USER, "Sent now"),
        Message("u5", Role.ASSISTANT, "The answer", model="m"),
    ]
    view.replace_messages(from_file)
    text = view.document.text
    assert view.GetInsertionPoint() == to_utf16(text, text.index("# You say: Sent now"))
    assert view.message_at_caret().message.id == "u4"  # type: ignore[union-attr]


def test_the_marks_can_be_removed_and_the_caret_stays_on_its_message(
    view: ConversationView,
) -> None:
    view.set_messages(
        [
            Message("1", Role.USER, "Say **this**"),
            Message("2", Role.ASSISTANT, "It is *so* **true**", model="m"),
        ]
    )
    view.SetInsertionPoint(view.document.spans[1].start + 5)  # in the answer
    view.set_without_marks(True)
    assert "**" not in view.GetValue()
    assert "It is so true" in view.GetValue()
    assert "# You say: Say this" in view.GetValue()  # the title too
    assert view.message_at_caret().message.id == "2"  # type: ignore[union-attr]
    assert view.shows(view._messages)  # the comparison uses the same option
    view.set_without_marks(False)
    assert "It is *so* **true**" in view.GetValue()
    assert view.message_at_caret().message.id == "2"  # type: ignore[union-attr]
