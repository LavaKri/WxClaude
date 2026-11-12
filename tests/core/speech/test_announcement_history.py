"""The history of the announcements: what it keeps, in what form, and what the center records."""

from datetime import datetime

import pytest

from wxclaude.core.speech.announcements import (
    Announce,
    AnnouncementCenter,
    Destination,
    RecordingMessageSink,
    RecordingSoundPlayer,
)
from wxclaude.core.speech.history import AnnouncementHistory

pytestmark = pytest.mark.unit


class Clock:
    """A clock that tells the minute it is given, to check the time of the lines."""

    def __init__(self) -> None:
        self.minute = 20

    def __call__(self) -> datetime:
        return datetime(2026, 11, 11, 10, self.minute, 30)


def test_a_line_is_the_time_then_the_text() -> None:
    clock = Clock()
    history = AnnouncementHistory(clock=clock)
    history.add("Ready")
    clock.minute = 5
    history.add("Claude has answered.")
    assert history.lines() == ["10:20 Ready", "10:05 Claude has answered."]


def test_the_same_announcement_twice_is_kept_twice() -> None:
    history = AnnouncementHistory()
    history.add("Claude is thinking.")
    history.add("Claude is thinking.")
    assert len(history) == 2


def test_a_change_comes_after_a_blank_line_but_not_at_the_start() -> None:
    clock = Clock()
    history = AnnouncementHistory(clock=clock)
    history.add_change("Workspace: WxClaude")
    history.add("Ready")
    clock.minute = 22
    history.add_change("Conversation: Fix")
    history.add("Ready")
    assert history.lines() == [
        "10:20 Workspace: WxClaude",
        "10:20 Ready",
        "",
        "10:22 Conversation: Fix",
        "10:22 Ready",
    ]


def test_a_message_on_several_lines_is_kept_on_one() -> None:
    history = AnnouncementHistory()
    history.add("Claude could not answer.\nThe server  refused\nthe key.")
    assert history.lines()[0].endswith("Claude could not answer. The server refused the key.")


def test_the_oldest_lines_go_first_when_the_limit_is_reached() -> None:
    history = AnnouncementHistory(limit=3)
    for number in range(5):
        history.add(f"line {number}")
    assert [line[6:] for line in history.lines()] == ["line 2", "line 3", "line 4"]


def test_a_change_that_became_the_first_line_has_no_blank_line_before() -> None:
    history = AnnouncementHistory(limit=2)
    history.add("one")
    history.add_change("Conversation: A")
    history.add("two")
    assert [line[6:] for line in history.lines()] == ["Conversation: A", "two"]


def test_the_center_records_every_announcement_even_when_nothing_is_said() -> None:
    center = AnnouncementCenter(destination_of=lambda category: Destination.NONE)
    center.notify(Announce.CLAUDE_THINKING, name="Claude")
    assert [line[6:] for line in center.history.lines()] == ["Claude is thinking."]


def test_the_history_says_more_about_a_tool_but_what_is_said_does_not_change() -> None:
    sink = RecordingMessageSink()
    center = AnnouncementCenter(
        message_sink=sink, destination_of=lambda category: Destination.MESSAGE
    )
    center.notify(
        Announce.CLAUDE_USING_TOOL,
        name="Claude",
        tool="Edit",
        target="build.bat",
        history_as=Announce.CLAUDE_USING_TOOL_ON,
    )
    assert sink.messages == ["Claude uses the tool Edit."]  # what the screen reader gets
    assert [line[6:] for line in center.history.lines()] == [
        "Claude uses the tool Edit on build.bat."
    ]


def test_without_a_target_the_history_keeps_the_text_that_is_said() -> None:
    center = AnnouncementCenter(destination_of=lambda category: Destination.NONE)
    center.notify(
        Announce.CLAUDE_USING_TOOL,
        name="Claude",
        tool="TodoWrite",
        history_as=Announce.CLAUDE_USING_TOOL_ON,
    )
    assert [line[6:] for line in center.history.lines()] == ["Claude uses the tool TodoWrite."]


def test_the_center_records_the_announcements_that_are_a_sound() -> None:
    player = RecordingSoundPlayer()
    center = AnnouncementCenter(
        destination_of=lambda category: Destination.SOUND_1, sound_player=player
    )
    center.notify(Announce.CLAUDE_DONE, name="Claude")
    assert player.played == [Destination.SOUND_1]
    assert [line[6:] for line in center.history.lines()] == ["Claude has answered."]


def test_the_center_records_a_dialog_once() -> None:
    shown: list[str] = []
    center = AnnouncementCenter(
        destination_of=lambda category: Destination.DIALOG, show_dialog=shown.append
    )
    center.notify(Announce.FOLDER_RESTRICTED)
    assert shown == ["Folder not trusted: restricted mode."]
    assert len(center.history) == 1


def test_a_movement_in_the_conversation_and_a_search_are_not_recorded() -> None:
    center = AnnouncementCenter()
    center.notify(Announce.MOVED_HEADING, title="Intro", level=1)
    center.notify(Announce.NO_NEXT_HEADING)
    center.notify(Announce.SEARCH_FOUND, line="a line")
    center.notify(Announce.SEARCH_NO_NEXT, term="x")
    assert len(center.history) == 0


def test_the_other_categories_are_recorded() -> None:
    center = AnnouncementCenter()
    center.notify(Announce.CLAUDE_USING_TOOL, name="Claude", tool="Read")
    center.notify(Announce.GAUGE_FIVE_HOUR, percent=91)
    center.notify(Announce.CONVERSATION_DELETED, name="Old")  # a fixed announcement
    assert len(center.history) == 3


def test_a_text_shown_another_way_and_a_change_can_be_recorded() -> None:
    center = AnnouncementCenter()
    center.record("Cannot save the workspace data.")
    center.record_change("Workspace: WxClaude")
    lines = center.history.lines()
    assert len(lines) == 3
    assert lines[0].endswith("Cannot save the workspace data.")
    assert lines[1] == ""
    assert lines[2].endswith("Workspace: WxClaude")
