from datetime import datetime

import pytest

from wxclaude.core.claude.events import RateLimit, RateWindow, TurnResult
from wxclaude.core.claude.usage import UsageTracker
from wxclaude.core.conversation.messages import Usage

pytestmark = pytest.mark.unit

NOW = datetime(2026, 10, 21, 14, 30)
LATER = datetime(2026, 10, 21, 16, 0)
TOMORROW = datetime(2026, 10, 22, 8, 0)


def _result(cost: float | None = 0.5, usage: Usage | None = None) -> TurnResult:
    return TurnResult(False, "success", "ok", usage or Usage(10, 47, 6765, 4293), 1654, cost, 1)


def _rate(*windows: RateWindow, status: str = "allowed") -> RateLimit:
    return RateLimit(status, "five_hour", windows)


def test_nothing_is_known_at_first() -> None:
    assert UsageTracker().lines(NOW) == [
        "No subscription usage information yet: it arrives with the next answer.",
        "No message sent yet in this conversation since it was opened here.",
    ]


def test_the_gauges_say_how_full_they_are_and_when_they_reset() -> None:
    tracker = UsageTracker()
    tracker.record_rate_limit(
        _rate(
            RateWindow("five_hour", 0.74, int(LATER.timestamp())),
            RateWindow("seven_day", 0.24, int(TOMORROW.timestamp())),
        ),
        NOW,
    )
    assert tracker.lines(NOW)[:3] == [
        "5-hour window, 74 % used, resets at 16:00.",
        "weekly window, 24 % used, resets at 2026-10-22 08:00.",
        "Gauges updated at 14:30.",
    ]


def test_a_window_missing_from_a_later_event_keeps_its_last_value() -> None:
    tracker = UsageTracker()
    both = _rate(RateWindow("five_hour", 0.1, None), RateWindow("seven_day", 0.2, None))
    tracker.record_rate_limit(both, NOW)
    tracker.record_rate_limit(_rate(RateWindow("five_hour", 0.3, None)), LATER)
    assert tracker.lines(LATER)[:2] == ["5-hour window, 30 % used.", "weekly window, 20 % used."]


def test_the_limit_status_is_only_given_when_it_is_not_allowed() -> None:
    tracker = UsageTracker()
    tracker.record_rate_limit(_rate(RateWindow("five_hour", 1.0, None), status="rejected"), NOW)
    assert "Limit status: rejected." in tracker.lines(NOW)


def test_an_unknown_window_is_named_as_it_comes() -> None:
    tracker = UsageTracker()
    tracker.record_rate_limit(_rate(RateWindow("mystery", None, None)), NOW)
    assert tracker.lines(NOW)[0] == "mystery."


def test_the_last_message_and_the_conversation_are_reported() -> None:
    tracker = UsageTracker()
    tracker.record_result(_result(0.25))
    tracker.record_result(_result(0.5, Usage(1, 2, 3, 4)))
    lines = tracker.lines(NOW)
    assert lines[1:] == [
        "Last message, tokens: 1 in, 2 out, 4 read from the cache, 3 written to the cache.",
        "Last message: cost 0.5000 dollars at list price, duration 1.7 seconds, turns: 1.",
        "Conversation since it was opened here, tokens: 11 in, 49 out, 4297 read from the cache,"
        " 6768 written to the cache.",
        "Conversation since it was opened here: cost 0.7500 dollars at list price, messages: 2.",
    ]


def test_an_unknown_cost_is_not_written() -> None:
    tracker = UsageTracker()
    result = TurnResult(False, "success", "", None, None, None, None)
    tracker.record_result(result)
    lines = tracker.lines(NOW)
    assert not any(line.startswith("Last message") for line in lines)


def test_a_new_conversation_starts_the_spending_again_but_keeps_the_gauges() -> None:
    tracker = UsageTracker()
    tracker.record_rate_limit(_rate(RateWindow("five_hour", 0.5, None)), NOW)
    tracker.record_result(_result())
    tracker.start_conversation()
    lines = tracker.lines(NOW)
    assert lines[0] == "5-hour window, 50 % used."
    assert lines[-1] == "No message sent yet in this conversation since it was opened here."
    assert tracker.conversation_turns == 0
