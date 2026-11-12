"""The sounds of the announcements: the files, and the player with ``winsound`` replaced."""

import sys
import winsound

import pytest

from wxclaude.core.errors import ScreenReaderOutputError
from wxclaude.core.speech.announcements import Destination
from wxclaude.core.speech.sounds import SOUND_FILES, WinsoundPlayer, sound_file

pytestmark = [
    pytest.mark.unit,
    pytest.mark.skipif(sys.platform != "win32", reason="winsound is a Windows module"),
]


@pytest.mark.parametrize("destination", list(SOUND_FILES))
def test_every_sound_destination_has_a_wav_file_in_the_package(destination: Destination) -> None:
    path = sound_file(destination)
    assert path.suffix == ".wav"
    assert path.is_file()


def test_the_two_sounds_are_two_different_files() -> None:
    assert sound_file(Destination.SOUND_1) != sound_file(Destination.SOUND_2)


def test_a_sound_is_started_in_the_background_without_being_played(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, int]] = []
    monkeypatch.setattr(winsound, "PlaySound", lambda name, flags: calls.append((name, flags)))
    WinsoundPlayer().play(Destination.SOUND_2)
    ((name, flags),) = calls
    assert name == str(sound_file(Destination.SOUND_2))
    assert flags == winsound.SND_FILENAME | winsound.SND_ASYNC


def test_a_sound_that_cannot_be_played_is_a_screen_reader_output_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(name: str, flags: int) -> None:
        raise RuntimeError("no sound device")

    monkeypatch.setattr(winsound, "PlaySound", fail)
    with pytest.raises(ScreenReaderOutputError, match=r"message\.wav: no sound device"):
        WinsoundPlayer().play(Destination.SOUND_1)
