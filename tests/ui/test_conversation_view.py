import pytest
import wx

from wxclaude.core.announcements import Announce
from wxclaude.core.messages import Message, Role
from wxclaude.ui.conversation_view import ConversationView

pytestmark = pytest.mark.ui


class _Said:
    def __init__(self) -> None:
        self.calls: list[tuple[Announce, dict[str, object]]] = []

    def __call__(self, announce: Announce, **values: object) -> None:
        self.calls.append((announce, values))


@pytest.fixture
def said() -> _Said:
    return _Said()


@pytest.fixture
def view(wx_app: wx.App, said: _Said):
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


def test_t_goes_to_the_next_heading_and_announces_it(view: ConversationView, said: _Said) -> None:
    _press(view, "T")
    assert view.GetInsertionPoint() == len("# You say: Hello\nHello\n\n")
    assert said.calls[-1] == (Announce.HEADING, {"title": "Answer from m", "level": 2})


def test_digit_goes_to_the_next_heading_of_that_level(view: ConversationView, said: _Said) -> None:
    _press(view, "1")
    assert said.calls[-1] == (Announce.HEADING, {"title": "You say: Again 😀", "level": 1})
    _press(view, "2", shift=True)
    assert said.calls[-1] == (Announce.HEADING, {"title": "Part", "level": 2})


def test_shift_goes_backwards_and_the_end_is_announced(view: ConversationView, said: _Said) -> None:
    _press(view, "T", shift=True)
    assert said.calls[-1][0] is Announce.NO_PREVIOUS_HEADING
    _press(view, "3")
    assert said.calls[-1] == (Announce.NO_NEXT_HEADING_OF_LEVEL, {"level": 3})


def test_positions_after_an_emoji_use_utf16_units(view: ConversationView, said: _Said) -> None:
    view.SetInsertionPoint(view.GetLastPosition())
    _press(view, "T", shift=True)
    title = said.calls[-1][1]["title"]
    assert title == "You say: Again 😀"
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
