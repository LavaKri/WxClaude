"""What the commands of the remote control do (``docs/remote.md``).

Nothing here touches wx or the pipe: a request that was already checked (``RemoteRequest``) is run
on the interface thread, with what it needs given by ``RemoteLinks``, and its response is a plain
dictionary. A message sent this way goes where a typed one goes (same agent, same permission
questions); it only leaves the prompt field and the focus alone.
"""

from collections.abc import Callable
from dataclasses import dataclass

from wxclaude.core.conversation.messages import Message, Role, Usage
from wxclaude.core.remote.protocol import (
    Command,
    ErrorCode,
    Field,
    RemoteRequest,
    failure,
    success,
    version_response,
)


@dataclass(frozen=True, slots=True)
class RemoteLinks:
    """What the presenter asks of the window.

    ``busy`` is true while Claude answers or the gauges are read (the send buttons are greyed
    then); ``answering`` only while a message is answered. ``send`` starts a message with the
    agent of the conversation and tells whether it started (the reason is already shown).
    ``messages`` are those of the conversation view, ``announcements`` the lines of the history.
    """

    has_conversation: Callable[[], bool]
    busy: Callable[[], bool]
    answering: Callable[[], bool]
    interrupt: Callable[[], None]
    send: Callable[[str], bool]
    messages: Callable[[], list[Message]]
    announcements: Callable[[], list[str]]


def tokens_of(usage: Usage) -> dict[str, int]:
    return {
        "input": usage.input_tokens,
        "output": usage.output_tokens,
        "cache_creation": usage.cache_creation_input_tokens,
        "cache_read": usage.cache_read_input_tokens,
    }


class RemotePresenter:
    """Runs the requests of the remote control."""

    def __init__(self, links: RemoteLinks) -> None:
        self._links = links

    def execute(self, request: RemoteRequest) -> dict[str, object]:
        """The response to ``request``."""
        if request.command is Command.INTERRUPT:
            self._links.interrupt()
            return success()
        if request.command is Command.SEND:
            return self._send(request.text)
        if request.command is Command.LAST:
            return success(**{field.value: self._field(field) for field in request.fields})
        if request.command is Command.VERSION:  # the endpoint answers it before this point
            return version_response()
        lines = [line for line in self._links.announcements() if line]  # no blank separators
        return success(lines=lines[-request.limit :])

    def _send(self, text: str) -> dict[str, object]:
        text = text.strip()
        if not text:
            return failure(ErrorCode.EMPTY_TEXT)
        if not self._links.has_conversation():
            return failure(ErrorCode.NO_CONVERSATION)
        if self._links.busy():
            return failure(ErrorCode.BUSY)
        if not self._links.send(text):
            return failure(ErrorCode.NOT_STARTED)
        return success()

    def _field(self, field: Field) -> object:
        if field is Field.STATUS:
            return "busy" if self._links.busy() else "idle"
        answer = self._last_answer()
        if answer is None:
            return None
        if field is Field.MESSAGE:
            return answer.text
        return None if answer.usage is None else tokens_of(answer.usage)

    def _last_answer(self) -> Message | None:
        """The last answer of Claude that is complete: while a message is answered, what has come
        in since it was sent is left out. Hidden messages (noise) do not count."""
        messages = self._links.messages()
        if self._links.answering():
            last_prompt = next(
                (i for i in range(len(messages) - 1, -1, -1) if messages[i].role is Role.USER), -1
            )
            messages = messages[: max(last_prompt, 0)]
        return next(
            (m for m in reversed(messages) if m.role is Role.ASSISTANT and not m.hidden), None
        )
