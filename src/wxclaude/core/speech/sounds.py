"""The sounds of the announcements: two WAV files played through the Windows sound API."""

import winsound
from importlib import resources
from pathlib import Path

from wxclaude.core.errors import ScreenReaderOutputError
from wxclaude.core.speech.announcements import Destination

#: The file (in ``wxclaude/sounds``) of each sound destination.
SOUND_FILES = {
    Destination.SOUND_1: "message.wav",
    Destination.SOUND_2: "permission.wav",
}


def sound_file(destination: Destination) -> Path:
    """The WAV file of the sound ``destination``."""
    name = SOUND_FILES[destination]
    return Path(str(resources.files("wxclaude").joinpath("sounds", name)))


class WinsoundPlayer:
    """Plays the sounds with ``winsound``, in the background (a new sound replaces the last)."""

    def play(self, destination: Destination) -> None:
        """Start the sound of ``destination``; raise ``ScreenReaderOutputError`` if it fails."""
        path = sound_file(destination)
        try:
            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
        except RuntimeError as error:
            raise ScreenReaderOutputError(f"{path.name}: {error}") from error
