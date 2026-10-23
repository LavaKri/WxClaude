from datetime import datetime

import pytest

from wxclaude.core.claude.events import RateLimit, RateWindow, TurnResult
from wxclaude.core.claude.usage import GaugeAlerts, UsageTracker
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
    """The CLI reports the total of the session: the cost of a message is the difference."""
    tracker = UsageTracker()
    tracker.start_conversation(0.0)
    tracker.record_result(_result(0.25))
    tracker.record_result(_result(0.75, Usage(1, 2, 3, 4)))
    lines = tracker.lines(NOW)
    assert lines[1:] == [
        "Last message, tokens: 1 in, 2 out, 4 read from the cache, 3 written to the cache.",
        "Last message: cost 0.5000 dollars at list price, duration 1.7 seconds, turns: 1.",
        "Conversation since it was opened here, tokens: 11 in, 49 out, 4297 read from the cache,"
        " 6768 written to the cache.",
        "Conversation since it was opened here: cost 0.7500 dollars at list price, messages: 2.",
    ]


def _costs(tracker: UsageTracker) -> tuple[float, float]:
    """The cost of the last message (-1 when it is not known) and of the conversation."""
    return (-1.0 if tracker.last_cost is None else tracker.last_cost), tracker.conversation_cost


def test_a_session_of_which_the_total_is_not_known_costs_nothing_to_the_first_message() -> None:
    tracker = UsageTracker()
    tracker.record_result(_result(0.40))  # 0.40 is the whole session, not this message
    assert _costs(tracker) == (-1.0, 0.0)
    assert "Last message: duration 1.7 seconds, turns: 1." in tracker.lines(NOW)
    tracker.record_result(_result(0.55))
    assert tracker.last_cost == pytest.approx(0.15)
    assert tracker.conversation_cost == pytest.approx(0.15)


def test_a_conversation_opened_with_its_total_counts_only_the_new_messages() -> None:
    tracker = UsageTracker()
    tracker.start_conversation(0.40)  # read from the session file
    tracker.record_result(_result(0.55))
    tracker.record_result(_result(0.60))
    assert tracker.last_cost == pytest.approx(0.05)
    assert tracker.conversation_cost == pytest.approx(0.20)
    assert tracker.conversation_turns == 2


def test_a_branch_goes_on_from_the_total_of_the_conversation_it_copies() -> None:
    tracker = UsageTracker()
    tracker.start_conversation(0.0)
    tracker.record_result(_result(0.25))
    tracker.start_conversation(tracker.session_total)  # the branch, before its first message
    assert _costs(tracker) == (-1.0, 0.0)
    tracker.record_result(_result(0.30))  # the CLI adds the 0.25 of the copied history
    assert tracker.last_cost == pytest.approx(0.05)
    assert tracker.conversation_cost == pytest.approx(0.05)


def test_a_total_that_went_down_is_not_a_cost() -> None:
    tracker = UsageTracker()
    tracker.start_conversation(0.50)
    tracker.record_result(_result(0.10))  # another session than the one expected
    assert _costs(tracker) == (-1.0, 0.0)
    tracker.record_result(_result(0.15))
    assert tracker.last_cost == pytest.approx(0.05)


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
    assert tracker.session_total is None
    lines = tracker.lines(NOW)
    assert lines[0] == "5-hour window, 50 % used."
    assert lines[-1] == "No message sent yet in this conversation since it was opened here."
    assert tracker.conversation_turns == 0


def test_a_gauge_is_announced_once_when_it_reaches_its_threshold() -> None:
    alerts = GaugeAlerts()
    assert alerts.update((RateWindow("five_hour", 0.5, 1),)) == []
    reached = RateWindow("five_hour", 0.9, 1)  # equal to the threshold counts
    assert alerts.update((reached,)) == [reached]
    assert alerts.update((RateWindow("five_hour", 0.95, 1),)) == []  # still over: not again
    assert alerts.update((RateWindow("five_hour", 0.99, 1),)) == []


def test_a_gauge_that_starts_again_is_announced_again() -> None:
    alerts = GaugeAlerts()
    assert len(alerts.update((RateWindow("five_hour", 0.92, 1),))) == 1
    assert alerts.update((RateWindow("five_hour", 0.0, 2),)) == []  # a new window of 5 hours
    assert len(alerts.update((RateWindow("five_hour", 0.91, 2),))) == 1
    assert len(alerts.update((RateWindow("five_hour", 0.1, 3),))) == 0
    assert len(alerts.update((RateWindow("five_hour", 0.95, 3),))) == 1


def test_the_week_has_three_thresholds_each_announced_once() -> None:
    alerts = GaugeAlerts()
    assert alerts.update((RateWindow("seven_day", 0.2, 1),)) == []
    assert len(alerts.update((RateWindow("seven_day", 0.26, 1),))) == 1  # 25 %
    assert alerts.update((RateWindow("seven_day", 0.4, 1),)) == []
    assert len(alerts.update((RateWindow("seven_day", 0.5, 1),))) == 1  # 50 %
    assert len(alerts.update((RateWindow("seven_day", 0.8, 1),))) == 1  # 75 %
    assert alerts.update((RateWindow("seven_day", 0.9, 1),)) == []  # nothing above 75 %
    assert alerts.update((RateWindow("seven_day", 0.1, 2),)) == []  # a new week
    assert len(alerts.update((RateWindow("seven_day", 0.3, 2),))) == 1  # 25 % again


def test_several_thresholds_passed_at_once_make_one_alert() -> None:
    alerts = GaugeAlerts()
    seen = RateWindow("seven_day", 0.63, 1)  # first reading of the application
    assert alerts.update((seen,)) == [seen]
    assert alerts.update((RateWindow("seven_day", 0.7, 1),)) == []


def test_each_gauge_has_its_own_state_and_unknown_ones_are_ignored() -> None:
    alerts = GaugeAlerts()
    week = RateWindow("seven_day", 0.75, 1)
    both = (RateWindow("five_hour", 0.3, 1), week, RateWindow("seven_day_opus", 0.99, 1))
    assert alerts.update(both) == [week]  # the 5 hours are low, Opus has no alert
    assert alerts.update((RateWindow("five_hour", 0.93, 1), week)) == [
        RateWindow("five_hour", 0.93, 1)
    ]
    assert alerts.update((RateWindow("five_hour", None, 1),)) == []  # unknown level


def test_ready_says_the_gauge_of_the_five_hours_when_it_is_known() -> None:
    tracker = UsageTracker()
    assert tracker.ready_line() == "Ready"
    tracker.record_rate_limit(_rate(RateWindow("seven_day", 0.2, 1)), NOW)
    assert tracker.ready_line() == "Ready"  # only the 5 hours count
    tracker.record_rate_limit(_rate(RateWindow("five_hour", 0.504, 1)), NOW)
    assert tracker.ready_line() == "Ready, gauge at 50 %"


def test_ready_adds_the_week_from_its_last_alert_threshold() -> None:
    tracker = UsageTracker()
    tracker.record_rate_limit(_rate(RateWindow("seven_day", 0.749, 1)), NOW)
    assert tracker.ready_line() == "Ready"  # 74.9 % is under the threshold
    tracker.record_rate_limit(_rate(RateWindow("seven_day", 0.76, 1)), NOW)
    assert tracker.ready_line() == "Ready, week at 76 %"
    tracker.record_rate_limit(_rate(RateWindow("five_hour", 0.5, 1)), NOW)
    assert tracker.ready_line() == "Ready, gauge at 50 %, week at 76 %"
    tracker.record_rate_limit(_rate(RateWindow("seven_day", 0.75, 1)), NOW)
    assert tracker.ready_line() == "Ready, gauge at 50 %, week at 75 %"
