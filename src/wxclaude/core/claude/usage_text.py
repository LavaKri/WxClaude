"""The text answered by the ``/usage`` command of the CLI, read as gauges.

The text is made for people (``Current session: 96% used · resets Oct 23, 1:50pm (Europe/Paris)``):
whole percentages, English, local time. Only the two gauges that matter are read; a line that is
not understood is left out, so a changed wording gives no gauge instead of a wrong one (see
``docs/claude-cli.md``, "Gauges without a message").
"""

import re
from datetime import datetime, timedelta

from wxclaude.core.claude.events import RateWindow

#: The text of ``/usage`` names these two gauges; they are the windows the reading can replace.
READ_WINDOWS = ("five_hour", "seven_day")

_LINE = re.compile(
    r"^\s*(?P<label>Current session|Current week \(all models\))\s*:\s*"
    r"(?P<percent>\d+(?:\.\d+)?)\s*%\s*used\b(?:\s*·\s*resets\s+(?P<reset>.*))?$",
    re.IGNORECASE,
)
_RESET = re.compile(
    r"^(?:(?P<month>[A-Za-z]{3,9})\s+(?P<day>\d{1,2})\s*,\s*)?"
    r"(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?P<half>[ap])m\b",
    re.IGNORECASE,
)
_NAMES = {"current session": "five_hour", "current week (all models)": "seven_day"}
_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")


def parse_usage(text: str, now: datetime) -> tuple[RateWindow, ...]:
    """The gauges named in ``text``; ``now`` places the reset times (which have no year)."""
    windows: list[RateWindow] = []
    for line in text.splitlines():
        found = _LINE.match(line.strip())
        if found is None:
            continue
        name = _NAMES[found["label"].lower()]
        resets_at = _reset_time(found["reset"] or "", now)
        windows.append(RateWindow(name, float(found["percent"]) / 100, resets_at))
    return tuple(windows)


def _reset_time(text: str, now: datetime) -> int | None:
    """``Oct 23, 1:50pm (Europe/Paris)`` or ``1:50pm`` as seconds since the epoch, local time."""
    found = _RESET.match(text.strip())
    if found is None:
        return None
    hour = int(found["hour"]) % 12 + (12 if found["half"].lower() == "p" else 0)
    minute = int(found["minute"] or 0)
    if found["month"] is None:
        moment = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return int((moment if moment >= now else moment + timedelta(days=1)).timestamp())
    short = found["month"][:3].lower()
    if short not in _MONTHS:
        return None
    month = _MONTHS.index(short) + 1
    try:
        moment = datetime(now.year, month, int(found["day"]), hour, minute)
        if moment < now - timedelta(days=1):  # a date that already passed is next year's
            moment = moment.replace(year=now.year + 1)
    except ValueError:
        return None
    return int(moment.timestamp())
