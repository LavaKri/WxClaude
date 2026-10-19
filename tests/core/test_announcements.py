import pytest

from wxclaude.core.announcements import (
    Announce,
    AnnouncementCenter,
    NullMessageSink,
    RecordingMessageSink,
)
from wxclaude.core.errors import ScreenReaderOutputError
from wxclaude.core.screen_reader import NONE, UIA, available_outputs, default_output, output_named

pytestmark = pytest.mark.unit


class _FailingSink:
    def show(self, text: str) -> None:
        raise ScreenReaderOutputError("broken")

    def close(self) -> None:
        pass


def test_notify_fills_the_text_and_sends_it() -> None:
    sink = RecordingMessageSink()
    center = AnnouncementCenter(sink)
    assert center.notify(Announce.WORKSPACE_OPENED, folder="C:\\work") == "Workspace: C:\\work"
    assert sink.messages == ["Workspace: C:\\work"]


def test_a_failing_sink_is_reported_once_then_replaced() -> None:
    errors: list[ScreenReaderOutputError] = []
    center = AnnouncementCenter(_FailingSink(), on_error=errors.append)
    center.notify(Announce.NEW_CONVERSATION)
    center.notify(Announce.NEW_CONVERSATION)
    assert len(errors) == 1
    assert isinstance(center.message_sink, NullMessageSink)


def test_outputs_depend_on_the_platform() -> None:
    assert available_outputs("win32") == (NONE, UIA)
    assert available_outputs("linux") == (NONE,)
    assert default_output("win32") is UIA
    assert default_output("linux") is NONE


def test_output_named_ignores_unavailable_outputs() -> None:
    assert output_named("uia", "win32") is UIA
    assert output_named("uia", "linux") is None
    assert output_named("unknown", "win32") is None
