"""Tests of the main window with the remote control on: the pipe, its commands, the title."""

import json
import os
import sys
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path

import pytest
import wx
from main_window_support import _Errors, _runner, _settings, _wait_until_idle

from wxclaude import __version__
from wxclaude.core.remote.pipe_server import PipeServer, pipe_name
from wxclaude.core.remote.protocol import PROTOCOL_VERSION
from wxclaude.ui.feedback import Feedback
from wxclaude.ui.main_window import MainWindow

pytestmark = [
    pytest.mark.ui,
    pytest.mark.skipif(sys.platform != "win32", reason="named pipes of Windows"),
]


def _pipe() -> str:
    return pipe_name(f"test-{os.getpid()}-{uuid.uuid4().hex[:8]}")


@pytest.fixture
def remote(
    wx_app: wx.App, destroy_after: Callable[[MainWindow], MainWindow], tmp_path: Path
) -> MainWindow:
    """A window with the remote control on, a workspace and a conversation."""
    window = destroy_after(MainWindow(_settings(), _runner(), remote_pipe=_pipe()))
    window.open_workspace(tmp_path)
    window._conversations.start_new("Notes")
    return window


def _ask(window: MainWindow, request: dict[str, object]) -> dict[str, object]:
    """Send ``request`` through the pipe from another thread, while the window handles events."""
    assert window._remote is not None
    name = window._remote._server.name
    answer: list[bytes] = []

    def client() -> None:
        with open(name, "r+b", buffering=0) as pipe:  # noqa: PTH123 (a pipe, not a file)
            pipe.write(json.dumps(request).encode("utf-8"))
            answer.append(pipe.read(1 << 20))

    thread = threading.Thread(target=client)
    thread.start()
    deadline = time.monotonic() + 15
    while thread.is_alive():
        assert time.monotonic() < deadline, "no answer from the pipe"
        wx.Yield()
        time.sleep(0.01)
    result = json.loads(answer[0])
    assert isinstance(result, dict)
    return result


def test_the_title_says_the_remote_control_is_on(remote: MainWindow, window: MainWindow) -> None:
    assert remote.GetTitle().startswith("Remote enabled - Notes - ")
    assert remote.GetTitle().endswith("WxClaude")
    assert "Remote" not in window.GetTitle()


def test_the_title_says_it_before_any_workspace(
    wx_app: wx.App, destroy_after: Callable[[MainWindow], MainWindow]
) -> None:
    window = destroy_after(MainWindow(_settings(), _runner(), remote_pipe=_pipe()))
    assert window.GetTitle() == "Remote enabled - WxClaude"


def test_a_pipe_that_cannot_be_created_leaves_the_window_without_remote(
    wx_app: wx.App,
    destroy_after: Callable[[MainWindow], MainWindow],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shown: list[str] = []
    # Before the window exists: it queues the call with the method it finds at that moment, and a
    # real message box would stay open on the screen of whoever runs the tests.
    monkeypatch.setattr(Feedback, "show_error", lambda self, message: shown.append(message))
    name = _pipe()
    taken = PipeServer(name, lambda request: request)
    taken.start()
    try:
        window = destroy_after(MainWindow(_settings(), _runner(), remote_pipe=name))
        wx.SafeYield()
        assert window._remote is None
        assert "Remote" not in window.GetTitle()
        assert len(shown) == 1
        assert shown[0].startswith("The remote control cannot start.")
    finally:
        taken.stop()


def test_closing_the_window_frees_the_pipe(
    wx_app: wx.App, destroy_after: Callable[[MainWindow], MainWindow]
) -> None:
    name = _pipe()
    window = destroy_after(MainWindow(_settings(), _runner(), remote_pipe=name))
    assert window._remote is not None
    window.Close()
    wx.SafeYield()
    again = PipeServer(name, lambda request: request)
    again.start()  # the name is free again
    again.stop()


def test_version_tells_which_application_answers(remote: MainWindow) -> None:
    assert _ask(remote, {"command": "version"}) == {
        "ok": True,
        "application": "WxClaude",
        "version": __version__,
        "protocol": PROTOCOL_VERSION,
    }


def test_last_before_any_message(remote: MainWindow) -> None:
    assert _ask(remote, {"command": "last"}) == {
        "ok": True,
        "message": None,
        "status": "idle",
        "tokens": None,
    }


def test_a_message_sent_through_the_pipe_is_answered_and_read_back(remote: MainWindow) -> None:
    errors = _Errors(remote)
    remote._prompt.SetValue("a draft the user is typing")
    assert _ask(remote, {"command": "send", "text": "hello remote"}) == {"ok": True}
    assert remote._run.busy
    _wait_until_idle(remote)
    assert errors.messages == []
    assert "Echo: hello remote" in remote._conversation.GetValue()
    assert remote._prompt.GetValue() == "a draft the user is typing"  # left alone
    result = _ask(remote, {"command": "last", "fields": ["message", "status"]})
    assert result == {"ok": True, "message": "Echo: hello remote", "status": "idle"}
    tokens = _ask(remote, {"command": "last", "fields": ["tokens"]})["tokens"]
    assert tokens is None or set(tokens) == {"input", "output", "cache_creation", "cache_read"}  # type: ignore[call-overload]


def test_a_second_message_is_refused_while_the_first_is_answered(
    remote: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_CLAUDE", "slow")
    assert _ask(remote, {"command": "send", "text": "first"}) == {"ok": True}
    assert _ask(remote, {"command": "send", "text": "second"}) == {"ok": False, "error": "busy"}
    assert _ask(remote, {"command": "last", "fields": ["status"]}) == {"ok": True, "status": "busy"}
    assert _ask(remote, {"command": "interrupt"}) == {"ok": True}
    _wait_until_idle(remote)


def test_interrupt_stops_the_message_like_the_button(
    remote: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_CLAUDE", "slow")
    errors = _Errors(remote)
    _ask(remote, {"command": "send", "text": "hello"})
    _ask(remote, {"command": "interrupt"})
    _wait_until_idle(remote)
    assert errors.messages == []
    lines = _ask(remote, {"command": "announcements", "limit": 5})["lines"]
    assert any("was interrupted" in line for line in lines)  # type: ignore[attr-defined]


def test_the_message_being_answered_is_not_given_as_the_last_one(
    remote: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ask(remote, {"command": "send", "text": "first"})
    _wait_until_idle(remote)
    monkeypatch.setenv("FAKE_CLAUDE", "slow")
    _ask(remote, {"command": "send", "text": "second"})
    result = _ask(remote, {"command": "last", "fields": ["message", "status"]})
    assert result == {"ok": True, "message": "Echo: first", "status": "busy"}
    _ask(remote, {"command": "interrupt"})
    _wait_until_idle(remote)


def test_send_without_a_conversation_is_refused(
    wx_app: wx.App, destroy_after: Callable[[MainWindow], MainWindow]
) -> None:
    window = destroy_after(MainWindow(_settings(), _runner(), remote_pipe=_pipe()))
    request: dict[str, object] = {"command": "send", "text": "hello"}
    assert _ask(window, request) == {"ok": False, "error": "no_conversation"}


def test_announcements_gives_what_was_said(remote: MainWindow) -> None:
    _ask(remote, {"command": "send", "text": "hello"})
    _wait_until_idle(remote)
    lines = _ask(remote, {"command": "announcements"})["lines"]
    assert isinstance(lines, list)
    assert any("has answered" in line for line in lines)


def test_bad_requests_get_an_error_not_silence(remote: MainWindow) -> None:
    assert _ask(remote, {"command": "delete"}) == {"ok": False, "error": "unknown_command"}
    assert _ask(remote, {"command": "last", "fields": ["secrets"]}) == {
        "ok": False,
        "error": "unknown_field",
    }
    assert _ask(remote, {"command": "send", "text": "   "}) == {"ok": False, "error": "empty_text"}
