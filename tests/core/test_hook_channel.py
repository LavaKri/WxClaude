import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator

import pytest

from wxclaude.core import hook_channel
from wxclaude.core.errors import RunnerError
from wxclaude.core.events import PermissionExpired, PermissionRequest, RunEvent
from wxclaude.core.hook_channel import HookChannel

pytestmark = pytest.mark.unit

BODY: dict[str, object] = {
    "hook_event_name": "PermissionRequest",
    "permission_mode": "default",
    "tool_name": "Bash",
    "tool_input": {"command": "touch x", "description": "Create x"},
    "permission_suggestions": [
        {
            "type": "addRules",
            "rules": [{"toolName": "Bash", "ruleContent": "touch x"}],
            "behavior": "allow",
            "destination": "localSettings",
        }
    ],
}


class Call:
    """One POST of the "CLI", made from its own thread because the server holds it."""

    def __init__(self, url: str, data: bytes) -> None:
        self.status = 0
        self.reply: object = None
        self._thread = threading.Thread(target=self._run, args=(url, data), daemon=True)
        self._thread.start()

    def _run(self, url: str, data: bytes) -> None:
        request = urllib.request.Request(url, data=data, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                self.status, raw = response.status, response.read()
        except urllib.error.HTTPError as error:
            self.status, raw = error.code, error.read()
        self.reply = json.loads(raw)

    def wait(self) -> None:
        self._thread.join(30)
        assert not self._thread.is_alive(), "the server never answered"


class Host:
    """A hook channel and what it reports."""

    def __init__(self, timeout_seconds: int = 600) -> None:
        self.events: list[RunEvent] = []
        self.asked = threading.Event()
        self.expired = threading.Event()
        self.channel = HookChannel(self._on_event, timeout_seconds)
        arguments = self.channel.arguments()
        assert arguments[0] == "--settings"
        hook = json.loads(arguments[1])["hooks"]["PermissionRequest"][0]["hooks"][0]
        self.url: str = hook["url"]

    def _on_event(self, event: RunEvent) -> None:
        self.events.append(event)
        if isinstance(event, PermissionRequest):
            self.asked.set()
        if isinstance(event, PermissionExpired):
            self.expired.set()

    def post(self, body: object = BODY, url: str | None = None) -> Call:
        data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        return Call(url or self.url, data)

    @property
    def request(self) -> PermissionRequest:
        assert self.asked.wait(30), "no question reached the interface"
        return next(event for event in self.events if isinstance(event, PermissionRequest))


@pytest.fixture
def host() -> Iterator[Host]:
    value = Host()
    yield value
    value.channel.close()


def test_the_arguments_hold_a_http_hook_on_the_loopback_with_a_token_and_the_timeout() -> None:
    value = Host(timeout_seconds=90)
    try:
        arguments = value.channel.arguments()
        hook = json.loads(arguments[1])["hooks"]["PermissionRequest"][0]["hooks"][0]
        assert hook["type"] == "http"
        assert hook["timeout"] == 90
        assert hook["url"].startswith("http://127.0.0.1:")
        assert "/hook/" in hook["url"]
        assert "--permission-prompt-tool" not in arguments
    finally:
        value.channel.close()


def test_a_question_reaches_the_interface_and_allow_is_the_response(host: Host) -> None:
    call = host.post()
    request = host.request
    assert request.tool_name == "Bash"
    assert request.input == BODY["tool_input"]
    assert request.suggested_rule == "Bash(touch x)"
    assert request.tool_use_id == ""
    assert request.description == ""
    host.channel.answer(request.request_id, {"behavior": "allow", "updatedInput": request.input})
    call.wait()
    assert call.status == 200
    assert call.reply == {
        "hookSpecificOutput": {
            "hookEventName": "PermissionRequest",
            "decision": {"behavior": "allow"},
        }
    }


def test_a_changed_input_is_sent_back(host: Host) -> None:
    call = host.post()
    request = host.request
    host.channel.answer(
        request.request_id, {"behavior": "allow", "updatedInput": {"command": "ls"}}
    )
    call.wait()
    assert isinstance(call.reply, dict)
    decision = call.reply["hookSpecificOutput"]["decision"]
    assert decision == {"behavior": "allow", "updatedInput": {"command": "ls"}}


def test_a_denial_carries_its_explanation(host: Host) -> None:
    call = host.post()
    request = host.request
    host.channel.answer(request.request_id, {"behavior": "deny", "message": "Not here"})
    call.wait()
    assert isinstance(call.reply, dict)
    assert call.reply["hookSpecificOutput"]["decision"] == {
        "behavior": "deny",
        "message": "Not here",
    }


def test_the_interface_may_answer_from_inside_the_event() -> None:
    channels: list[HookChannel] = []

    def answer_at_once(event: RunEvent) -> None:
        if isinstance(event, PermissionRequest):
            channels[0].answer(event.request_id, {"behavior": "deny", "message": "no"})

    channel = HookChannel(answer_at_once, 600)
    channels.append(channel)
    try:
        url = json.loads(channel.arguments()[1])["hooks"]["PermissionRequest"][0]["hooks"][0]["url"]
        call = Call(url, json.dumps(BODY).encode("utf-8"))
        call.wait()
        assert isinstance(call.reply, dict)
        assert call.reply["hookSpecificOutput"]["decision"] == {"behavior": "deny", "message": "no"}
    finally:
        channel.close()


def test_a_wrong_token_a_broken_body_and_a_big_body_are_refused(
    host: Host, monkeypatch: pytest.MonkeyPatch
) -> None:
    wrong = host.url.rsplit("/", 1)[0] + "/not-the-token"
    for call, status in (
        (host.post(url=wrong), 404),
        (host.post(b"not json"), 400),
        (host.post(b"[1, 2]"), 400),
    ):
        call.wait()
        assert call.status == status
    monkeypatch.setattr(hook_channel, "MAX_BODY_BYTES", 10)
    big = host.post()
    big.wait()
    assert big.status == 413
    assert not any(isinstance(event, PermissionRequest) for event in host.events)


def test_closing_the_channel_ends_the_questions_without_a_decision(host: Host) -> None:
    call = host.post()
    assert host.request
    host.channel.close()
    call.wait()
    assert call.status == 200
    assert call.reply == {}


def test_a_question_nobody_answers_expires_and_can_no_longer_be_answered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(hook_channel, "_EXPIRY_MARGIN_SECONDS", 0)
    value = Host(timeout_seconds=0)
    try:
        call = value.post()
        call.wait()
        assert call.reply == {}
        assert value.expired.wait(30)
        request = value.request
        expired = next(event for event in value.events if isinstance(event, PermissionExpired))
        assert (expired.request_id, expired.tool_name) == (request.request_id, "Bash")
        with pytest.raises(RunnerError):
            value.channel.answer(request.request_id, {"behavior": "allow"})
    finally:
        value.channel.close()


def test_answering_an_unknown_question_is_an_error(host: Host) -> None:
    with pytest.raises(RunnerError):
        host.channel.answer("nope", {"behavior": "allow"})
