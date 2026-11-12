"""What the remote commands do, with fake links: no wx, no pipe."""

import pytest

from wxclaude.core.conversation.messages import Message, Role, Usage
from wxclaude.core.remote.protocol import Command, Field, RemoteRequest, version_response
from wxclaude.presenters.remote_presenter import RemoteLinks, RemotePresenter

pytestmark = pytest.mark.unit

USAGE = Usage(input_tokens=1200, output_tokens=340, cache_read_input_tokens=800)


class FakeWindow:
    """What the links of the window give, and a record of what the commands asked."""

    def __init__(self) -> None:
        self.conversation = True
        self.busy = False
        self.answering = False
        self.starts = True
        self.messages: list[Message] = []
        self.lines: list[str] = []
        self.interrupted = 0
        self.sent: list[str] = []

    def links(self) -> RemoteLinks:
        return RemoteLinks(
            has_conversation=lambda: self.conversation,
            busy=lambda: self.busy,
            answering=lambda: self.answering,
            interrupt=self._interrupt,
            send=self._send,
            messages=lambda: list(self.messages),
            announcements=lambda: list(self.lines),
        )

    def _interrupt(self) -> None:
        self.interrupted += 1

    def _send(self, text: str) -> bool:
        self.sent.append(text)
        return self.starts


def _presenter(window: FakeWindow) -> RemotePresenter:
    return RemotePresenter(window.links())


def _last(window: FakeWindow, *fields: Field) -> dict[str, object]:
    request = RemoteRequest(Command.LAST, fields=fields or tuple(Field))
    return _presenter(window).execute(request)


def _prompt(text: str = "Question") -> Message:
    return Message("u", Role.USER, text)


def _answer(text: str, usage: Usage | None = USAGE, *, hidden: bool = False) -> Message:
    return Message("a", Role.ASSISTANT, text, model="haiku", usage=usage, hidden=hidden)


def test_interrupt_uses_the_interrupt_of_the_window() -> None:
    window = FakeWindow()
    assert _presenter(window).execute(RemoteRequest(Command.INTERRUPT)) == {"ok": True}
    assert window.interrupted == 1


def test_interrupt_is_fine_when_nothing_is_running() -> None:
    window = FakeWindow()
    assert _presenter(window).execute(RemoteRequest(Command.INTERRUPT))["ok"] is True


def test_send_starts_the_message_with_its_text_trimmed() -> None:
    window = FakeWindow()
    response = _presenter(window).execute(RemoteRequest(Command.SEND, text="  Hello\n"))
    assert response == {"ok": True}
    assert window.sent == ["Hello"]


@pytest.mark.parametrize(
    ("change", "error"),
    [
        ({"conversation": False}, "no_conversation"),
        ({"busy": True}, "busy"),
        ({"starts": False}, "not_started"),
    ],
)
def test_send_says_why_it_did_not_start(change: dict[str, bool], error: str) -> None:
    window = FakeWindow()
    for name, value in change.items():
        setattr(window, name, value)
    response = _presenter(window).execute(RemoteRequest(Command.SEND, text="Hello"))
    assert response == {"ok": False, "error": error}


def test_send_refuses_a_text_with_nothing_in_it_before_anything_else() -> None:
    window = FakeWindow()
    window.conversation = False
    response = _presenter(window).execute(RemoteRequest(Command.SEND, text="  \n "))
    assert response == {"ok": False, "error": "empty_text"}
    assert window.sent == []


def test_last_gives_the_message_the_status_and_the_tokens() -> None:
    window = FakeWindow()
    window.messages = [_prompt(), _answer("Hi there")]
    assert _last(window) == {
        "ok": True,
        "message": "Hi there",
        "status": "idle",
        "tokens": {"input": 1200, "output": 340, "cache_creation": 0, "cache_read": 800},
    }


def test_last_only_gives_the_fields_asked() -> None:
    window = FakeWindow()
    window.messages = [_prompt(), _answer("Hi")]
    assert _last(window, Field.STATUS) == {"ok": True, "status": "idle"}


def test_last_has_no_message_and_no_tokens_before_the_first_answer() -> None:
    window = FakeWindow()
    assert _last(window) == {"ok": True, "message": None, "status": "idle", "tokens": None}
    window.messages = [_prompt()]
    assert _last(window)["message"] is None


def test_an_answer_without_usage_has_no_tokens() -> None:
    window = FakeWindow()
    window.messages = [_prompt(), _answer("Hi", usage=None)]
    result = _last(window)
    assert (result["message"], result["tokens"]) == ("Hi", None)


def test_the_status_is_busy_while_the_window_is_busy() -> None:
    window = FakeWindow()
    window.busy = True
    assert _last(window, Field.STATUS)["status"] == "busy"


def test_the_answer_being_written_is_not_the_last_message() -> None:
    window = FakeWindow()
    window.busy = window.answering = True
    window.messages = [
        _prompt("First"),
        _answer("Old answer"),
        _prompt("Second"),
        _answer("Half of the new one", usage=None),
    ]
    result = _last(window)
    assert (result["message"], result["status"]) == ("Old answer", "busy")
    assert result["tokens"] == {
        "input": 1200,
        "output": 340,
        "cache_creation": 0,
        "cache_read": 800,
    }


def test_reading_the_gauges_does_not_hide_the_last_answer() -> None:
    window = FakeWindow()
    window.busy = True  # the gauges are read: no message is being answered
    window.messages = [_prompt(), _answer("Done")]
    result = _last(window)
    assert (result["message"], result["status"]) == ("Done", "busy")


def test_the_first_answer_being_written_leaves_no_last_message() -> None:
    window = FakeWindow()
    window.busy = window.answering = True
    window.messages = [_prompt(), _answer("Beginning", usage=None)]
    assert _last(window, Field.MESSAGE) == {"ok": True, "message": None}


def test_hidden_messages_do_not_count() -> None:
    window = FakeWindow()
    window.messages = [
        _prompt(),
        _answer("Real answer"),
        _answer("No response requested.", hidden=True),
    ]
    assert _last(window, Field.MESSAGE)["message"] == "Real answer"


def test_announcements_gives_the_last_lines_without_the_blank_separators() -> None:
    window = FakeWindow()
    window.lines = ["10:00 Ready", "", "10:01 Workspace: A", "10:02 Claude is thinking"]
    request = RemoteRequest(Command.ANNOUNCEMENTS, limit=2)
    assert _presenter(window).execute(request) == {
        "ok": True,
        "lines": ["10:01 Workspace: A", "10:02 Claude is thinking"],
    }


def test_version_gives_the_application_and_the_protocol() -> None:
    response = _presenter(FakeWindow()).execute(RemoteRequest(Command.VERSION))
    assert response == version_response()
    assert response["application"] == "WxClaude"


def test_announcements_gives_all_it_has_when_the_limit_is_larger() -> None:
    window = FakeWindow()
    window.lines = ["10:00 Ready"]
    request = RemoteRequest(Command.ANNOUNCEMENTS, limit=50)
    assert _presenter(window).execute(request)["lines"] == ["10:00 Ready"]
