import json

import pytest

from wxclaude import __version__
from wxclaude.core.errors import RemoteRequestError
from wxclaude.core.remote.protocol import (
    DEFAULT_ANNOUNCEMENTS,
    MAX_ANNOUNCEMENTS,
    PROTOCOL_VERSION,
    Command,
    ErrorCode,
    Field,
    encode,
    failure,
    parse_request,
    success,
    version_response,
)

pytestmark = pytest.mark.unit


def _refusal(raw: bytes) -> str:
    with pytest.raises(RemoteRequestError) as caught:
        parse_request(raw)
    return caught.value.code


def test_interrupt_needs_nothing_else() -> None:
    request = parse_request(b'{"command": "interrupt"}')
    assert request.command is Command.INTERRUPT


def test_version_needs_nothing_else() -> None:
    assert parse_request(b'{"command": "version"}').command is Command.VERSION


def test_the_version_response_names_the_application_its_version_and_the_protocol() -> None:
    response = version_response()
    assert response == {
        "ok": True,
        "application": "WxClaude",
        "version": __version__,
        "protocol": PROTOCOL_VERSION,
    }
    assert isinstance(PROTOCOL_VERSION, int)


def test_send_carries_its_text() -> None:
    request = parse_request('{"command": "send", "text": "Bonjour é"}'.encode())
    assert (request.command, request.text) == (Command.SEND, "Bonjour é")


def test_last_gives_every_field_unless_told_which() -> None:
    assert parse_request(b'{"command": "last"}').fields == tuple(Field)
    request = parse_request(b'{"command": "last", "fields": ["tokens", "status", "tokens"]}')
    assert request.fields == (Field.TOKENS, Field.STATUS)  # in the order asked, once each


def test_announcements_has_a_default_and_a_maximum_limit() -> None:
    assert parse_request(b'{"command": "announcements"}').limit == DEFAULT_ANNOUNCEMENTS
    assert parse_request(b'{"command": "announcements", "limit": 7}').limit == 7
    huge = parse_request(b'{"command": "announcements", "limit": 99999}')
    assert huge.limit == MAX_ANNOUNCEMENTS


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"not json",
        b"\xff\xfe",  # not UTF-8
        b"[1, 2]",  # not an object
        b'"interrupt"',
        b'{"command": "send"}',  # the text is missing
        b'{"command": "send", "text": 5}',
        b'{"command": "last", "fields": "status"}',  # not a list
        b'{"command": "last", "fields": []}',
        b'{"command": "announcements", "limit": 0}',
        b'{"command": "announcements", "limit": "5"}',
        b'{"command": "announcements", "limit": true}',
    ],
)
def test_a_malformed_request_is_invalid(raw: bytes) -> None:
    assert _refusal(raw) == ErrorCode.INVALID_REQUEST


@pytest.mark.parametrize(
    "raw",
    [b"{}", b'{"command": "Interrupt"}', b'{"command": "quit"}', b'{"command": ["last"]}'],
)
def test_only_the_five_commands_exist_with_their_exact_name(raw: bytes) -> None:
    assert _refusal(raw) == ErrorCode.UNKNOWN_COMMAND


@pytest.mark.parametrize("fields", ['["model"]', '["status", "other"]', "[1]", "[[]]"])
def test_an_unknown_field_is_named_as_such(fields: str) -> None:
    raw = f'{{"command": "last", "fields": {fields}}}'.encode()
    assert _refusal(raw) == ErrorCode.UNKNOWN_FIELD


def test_responses_are_ascii_json() -> None:
    raw = encode(success(message="é à"))
    assert raw.isascii()
    assert json.loads(raw) == {"ok": True, "message": "é à"}
    assert json.loads(encode(failure(ErrorCode.BUSY))) == {"ok": False, "error": "busy"}
