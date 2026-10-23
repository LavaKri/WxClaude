from datetime import datetime

import pytest

from wxclaude.core.claude.events import RateWindow
from wxclaude.core.claude.usage_text import parse_usage

pytestmark = pytest.mark.unit

NOW = datetime(2026, 10, 23, 10, 0)
TEXT = (
    "Current session: 96% used · resets Oct 23, 1:50pm (Europe/Paris)\n"
    "Current week (all models): 67% used · resets Oct 26, 1am (Europe/Paris)\n"
    "\n"
    "What's contributing to your limits usage?\n"
    "Approximate, based on local sessions on this machine.\n"
)


def _at(month: int, day: int, hour: int, minute: int = 0) -> int:
    return int(datetime(2026, month, day, hour, minute).timestamp())


def test_the_session_and_the_week_are_read() -> None:
    assert parse_usage(TEXT, NOW) == (
        RateWindow("five_hour", 0.96, _at(10, 23, 13, 50)),
        RateWindow("seven_day", 0.67, _at(10, 26, 1)),
    )


def test_noon_and_midnight() -> None:
    text = "Current session: 1% used · resets Oct 24, 12am\n"
    text += "Current week (all models): 2% used · resets Oct 24, 12:30pm\n"
    first, second = parse_usage(text, NOW)
    assert first.resets_at == _at(10, 24, 0)
    assert second.resets_at == _at(10, 24, 12, 30)


def test_a_reset_in_january_seen_in_december_is_next_year() -> None:
    december = datetime(2026, 12, 30, 10, 0)
    (window,) = parse_usage("Current session: 10% used · resets Jan 2, 3am\n", december)
    assert window.resets_at == int(datetime(2027, 1, 2, 3).timestamp())


def test_a_time_alone_is_today_or_tomorrow() -> None:
    later, earlier = (
        parse_usage(f"Current session: 5% used · resets {when}\n", NOW)[0].resets_at
        for when in ("1:50pm (Europe/Paris)", "9am")
    )
    assert later == _at(10, 23, 13, 50)
    assert earlier == _at(10, 24, 9)


def test_a_gauge_without_a_reset_or_with_an_unknown_one_has_no_time() -> None:
    text = "Current session: 0% used\nCurrent week (all models): 3% used · resets someday\n"
    assert parse_usage(text, NOW) == (
        RateWindow("five_hour", 0.0, None),
        RateWindow("seven_day", 0.03, None),
    )


@pytest.mark.parametrize(
    "text",
    [
        "",
        "Nothing to see here.",
        "Current session: unknown",
        "Current week (Sonnet only): 10% used",
        "Usage: 96% used",
    ],
)
def test_a_text_that_is_not_understood_gives_no_gauge(text: str) -> None:
    assert parse_usage(text, NOW) == ()
