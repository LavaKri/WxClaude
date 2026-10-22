import pytest

from wxclaude.core.announcements import (
    CATEGORIES,
    END_OF_ANSWER,
    HEADINGS,
    PERMISSION_QUESTION,
    PROGRESS,
    Announce,
    AnnouncementCenter,
    Category,
    Destination,
    NullMessageSink,
    NullSoundPlayer,
    RecordingMessageSink,
    RecordingSoundPlayer,
)
from wxclaude.core.errors import ScreenReaderOutputError
from wxclaude.core.screen_reader import NONE, UIA, available_outputs, default_output, output_named
from wxclaude.core.sounds import SOUND_FILES, sound_file

pytestmark = pytest.mark.unit


class _FailingSink:
    def show(self, text: str) -> None:
        raise ScreenReaderOutputError("broken")

    def close(self) -> None:
        pass


class _FailingPlayer:
    def play(self, destination: Destination) -> None:
        raise ScreenReaderOutputError("no sound")


def _center(
    destinations: dict[Category, Destination] | None = None,
) -> tuple[AnnouncementCenter, RecordingMessageSink, RecordingSoundPlayer]:
    sink, player = RecordingMessageSink(), RecordingSoundPlayer()
    chosen = destinations or {}
    center = AnnouncementCenter(
        sink, lambda category: chosen.get(category, category.default), sound_player=player
    )
    return center, sink, player


def test_notify_fills_the_text_and_sends_it() -> None:
    center, sink, _player = _center()
    assert center.notify(Announce.CLAUDE_USING_TOOL, tool="Read") == "Claude uses the tool Read."
    assert sink.messages == ["Claude uses the tool Read."]


def test_a_fixed_announcement_is_always_a_message() -> None:
    center, sink, _player = _center()
    center.notify(Announce.NO_CONVERSATION)
    assert sink.messages == ["No conversation in this workspace."]


def test_none_says_nothing() -> None:
    center, sink, player = _center({PROGRESS: Destination.NONE})
    assert center.notify(Announce.CLAUDE_THINKING) is None
    assert (sink.messages, player.played) == ([], [])


def test_a_sound_is_played_and_no_text_is_returned() -> None:
    center, sink, player = _center()
    assert center.notify(Announce.CLAUDE_DONE) is None
    assert center.notify(Announce.PERMISSION_ASKED, tool="Bash") is None
    assert player.played == [Destination.SOUND_1, Destination.SOUND_2]
    assert sink.messages == []


def test_read_line_sends_the_line() -> None:
    center, sink, _player = _center({HEADINGS: Destination.READ_LINE})
    center.notify(Announce.HEADING, title="Part", level=2, line="Part")
    assert sink.messages == ["Part"]


def test_a_destination_the_category_does_not_accept_gives_the_default() -> None:
    center, _sink, _player = _center({PROGRESS: Destination.SOUND_1})
    assert center.destination(Announce.CLAUDE_THINKING) is PROGRESS.default


def test_the_defaults_are_the_chosen_ones() -> None:
    assert END_OF_ANSWER.default is Destination.SOUND_1
    assert PERMISSION_QUESTION.default is Destination.SOUND_2
    for category in CATEGORIES:
        assert category.accepts(category.default)
        assert category.choices[0] is Destination.NONE


def test_every_announcement_category_is_listed() -> None:
    used = {announce.category for announce in Announce if announce.category is not None}
    assert used == set(CATEGORIES)


def test_a_failing_sink_is_reported_once_then_replaced() -> None:
    errors: list[ScreenReaderOutputError] = []
    center = AnnouncementCenter(_FailingSink(), on_error=errors.append)
    center.notify(Announce.CLAUDE_THINKING)
    center.notify(Announce.CLAUDE_THINKING)
    assert len(errors) == 1
    assert isinstance(center.message_sink, NullMessageSink)


def test_a_failing_sound_is_reported_once_then_replaced() -> None:
    errors: list[ScreenReaderOutputError] = []
    center = AnnouncementCenter(sound_player=_FailingPlayer(), on_error=errors.append)
    center.notify(Announce.CLAUDE_DONE)
    center.notify(Announce.CLAUDE_DONE)
    assert len(errors) == 1
    assert isinstance(center.sound_player, NullSoundPlayer)


def test_each_sound_has_its_file() -> None:
    assert set(SOUND_FILES) == {Destination.SOUND_1, Destination.SOUND_2}
    for destination in SOUND_FILES:
        assert sound_file(destination).is_file()


def test_outputs_depend_on_the_platform() -> None:
    assert available_outputs("win32") == (NONE, UIA)
    assert available_outputs("linux") == (NONE,)
    assert default_output("win32") is UIA
    assert default_output("linux") is NONE


def test_output_named_ignores_unavailable_outputs() -> None:
    assert output_named("uia", "win32") is UIA
    assert output_named("uia", "linux") is None
    assert output_named("unknown", "win32") is None
