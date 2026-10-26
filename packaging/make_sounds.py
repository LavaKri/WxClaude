"""Make the two sounds of the announcements (message.wav and permission.wav) by synthesis.

Usage: python packaging/make_sounds.py <output folder>   (all the candidates, to listen to)
       python packaging/make_sounds.py --install          (the chosen ones, into the package)

Every sound is made here from sine waves, so it belongs to the project and follows its license. The
candidates are named ``message-a.wav``, ``permission-b.wav``...; ``CHOSEN`` says which ones the
application uses: ``--install`` writes them to ``src/wxclaude/sounds`` under the names it reads.
Stereo, 48 kHz, 16 bits, moderate volume (the voice of a screen reader must stay clear).
"""

import math
import struct
import sys
import wave
from collections.abc import Sequence
from pathlib import Path

RATE = 48000
PEAK = 0.19683  # fraction of the full scale: quiet, so as not to cover the voice of a screen reader

# A note is (frequency in Hz, length in seconds). Bell partials: ratio and weight.
_PURE = ((1.0, 1.0), (2.0, 0.15))
_BELL = ((1.0, 1.0), (2.76, 0.35), (5.4, 0.12))
Note = tuple[float, float]


def _note(frequency: float, length: float, partials: Sequence[tuple[float, float]], bell: bool):
    """The samples of one note: a soft attack, then a fade (an exponential decay for a bell)."""
    count = int(RATE * length)
    attack = int(RATE * 0.01)
    release = int(RATE * min(0.08, length / 3))
    samples = []
    for index in range(count):
        time = index / RATE
        value = sum(
            weight * math.sin(2 * math.pi * frequency * ratio * time) for ratio, weight in partials
        )
        value /= sum(weight for _, weight in partials)
        envelope = min(1.0, index / attack)
        if bell:
            envelope *= math.exp(-4.5 * time / length)
        elif index > count - release:
            envelope *= (count - index) / release
        samples.append(value * envelope)
    return samples


def render(notes: Sequence[Note], *, bell: bool, gap: float = 0.03) -> list[float]:
    """The notes one after the other, with a short silence between them."""
    partials = _BELL if bell else _PURE
    samples: list[float] = []
    for frequency, length in notes:
        samples += _note(frequency, length, partials, bell)
        samples += [0.0] * int(RATE * gap)
    return samples


def write(path: Path, samples: Sequence[float]) -> None:
    """Write ``samples`` (between -1 and 1) as a stereo 16-bit WAV file, at the quiet volume."""
    peak = max(abs(value) for value in samples) or 1.0
    scale = PEAK / peak * 32767
    frames = b"".join(struct.pack("<hh", *(int(value * scale),) * 2) for value in samples)
    with wave.open(str(path), "wb") as file:
        file.setnchannels(2)
        file.setsampwidth(2)
        file.setframerate(RATE)
        file.writeframes(frames)


# Frequencies: C5 523, G5 784, A5 880, B5 988.
CANDIDATES: dict[str, list[float]] = {
    # The end of an answer: one bell note, a "ting" (A5).
    "message-1": render([(880.0, 0.45)], bell=True),
    # A question of permission: two pure notes that rise, C5 then G5, played once.
    "permission-1": render([(523.25, 0.16), (783.99, 0.28)], bell=False),
}


# The sound of the application -> the candidate that was chosen.
CHOSEN = {"message": "message-1", "permission": "permission-1"}
PACKAGE_FOLDER = Path(__file__).resolve().parent.parent / "src" / "wxclaude" / "sounds"


def main() -> int:
    if len(sys.argv) != 2:
        sys.stderr.write("Usage: python packaging/make_sounds.py <output folder> | --install\n")
        return 2
    if sys.argv[1] == "--install":
        PACKAGE_FOLDER.mkdir(parents=True, exist_ok=True)
        for name, candidate in CHOSEN.items():
            write(PACKAGE_FOLDER / f"{name}.wav", CANDIDATES[candidate])
            sys.stdout.write(f"{name}.wav = {candidate}\n")
        return 0
    folder = Path(sys.argv[1])
    folder.mkdir(parents=True, exist_ok=True)
    for name, samples in CANDIDATES.items():
        write(folder / f"{name}.wav", samples)
        sys.stdout.write(f"{name}.wav: {len(samples) / RATE:.2f} s\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
