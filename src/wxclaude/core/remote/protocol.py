"""The messages of the remote control (see ``docs/remote.md``).

A client sends one JSON object, ``{"command": "last", "fields": ["status"]}``, and receives one
JSON object, ``{"ok": true, ...}`` or ``{"ok": false, "error": "busy"}``. Only the commands
below exist; anything else is refused before it reaches the application. Responses are written
with ASCII escapes so that a client reading them with another code page still gets the right text.
"""

import json
from dataclasses import dataclass
from enum import StrEnum

from wxclaude import __version__
from wxclaude.core.errors import RemoteRequestError

PROTOCOL_VERSION = 1  # raised when a command or a response changes in a way a client can notice
MAX_REQUEST_BYTES = 256 * 1024
DEFAULT_ANNOUNCEMENTS = 50
MAX_ANNOUNCEMENTS = 500  # what the history of the announcements keeps


class Command(StrEnum):
    INTERRUPT = "interrupt"
    SEND = "send"
    LAST = "last"
    ANNOUNCEMENTS = "announcements"
    VERSION = "version"


class Field(StrEnum):
    """What the command ``last`` can give."""

    MESSAGE = "message"
    STATUS = "status"
    TOKENS = "tokens"


class ErrorCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
    UNKNOWN_COMMAND = "unknown_command"
    UNKNOWN_FIELD = "unknown_field"
    BUSY = "busy"
    NO_CONVERSATION = "no_conversation"
    EMPTY_TEXT = "empty_text"
    NOT_STARTED = "not_started"
    TIMEOUT = "timeout"
    INTERNAL = "internal_error"


@dataclass(frozen=True, slots=True)
class RemoteRequest:
    """A request that was checked: a known command and the values it needs."""

    command: Command
    text: str = ""  # ``send``
    fields: tuple[Field, ...] = tuple(Field)  # ``last``
    limit: int = DEFAULT_ANNOUNCEMENTS  # ``announcements``


def parse_request(raw: bytes) -> RemoteRequest:
    """The request in ``raw``; ``RemoteRequestError`` (with the code for the client) if it is not
    an object with a known command and valid values."""
    try:
        body = json.loads(raw.decode("utf-8"))
    except ValueError as error:  # includes UnicodeDecodeError and JSONDecodeError
        raise RemoteRequestError(ErrorCode.INVALID_REQUEST) from error
    if not isinstance(body, dict):
        raise RemoteRequestError(ErrorCode.INVALID_REQUEST)
    name = body.get("command")
    try:
        command = Command(name if isinstance(name, str) else "")
    except ValueError as error:
        raise RemoteRequestError(ErrorCode.UNKNOWN_COMMAND) from error
    if command is Command.SEND:
        return RemoteRequest(command, text=_text(body.get("text")))
    if command is Command.LAST:
        return RemoteRequest(command, fields=_fields(body.get("fields")))
    if command is Command.ANNOUNCEMENTS:
        return RemoteRequest(command, limit=_limit(body.get("limit")))
    return RemoteRequest(command)


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise RemoteRequestError(ErrorCode.INVALID_REQUEST)
    return value


def _fields(value: object) -> tuple[Field, ...]:
    """The fields asked for; all of them when the request names none."""
    if value is None:
        return tuple(Field)
    if not isinstance(value, list) or not value:
        raise RemoteRequestError(ErrorCode.INVALID_REQUEST)
    try:
        return tuple(dict.fromkeys(Field(name) for name in value))  # no repeat, order kept
    except ValueError as error:
        raise RemoteRequestError(ErrorCode.UNKNOWN_FIELD) from error


def _limit(value: object) -> int:
    if value is None:
        return DEFAULT_ANNOUNCEMENTS
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise RemoteRequestError(ErrorCode.INVALID_REQUEST)
    return min(value, MAX_ANNOUNCEMENTS)


def version_response() -> dict[str, object]:
    """What ``version`` answers: the application, its version and the version of this protocol."""
    return success(application="WxClaude", version=__version__, protocol=PROTOCOL_VERSION)


def success(**fields: object) -> dict[str, object]:
    """A response that worked, with what the command returns."""
    return {"ok": True, **fields}


def failure(code: str) -> dict[str, object]:
    """A response that failed, with the error code."""
    return {"ok": False, "error": str(code)}


def encode(response: dict[str, object]) -> bytes:
    return json.dumps(response).encode("ascii")
