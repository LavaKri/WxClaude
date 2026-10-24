"""The totals of a session as the CLI writes them (``cost-state`` entries)."""

import pytest

from wxclaude.core.claude.cost_state import CostState, ModelTotals, parse_cost_state
from wxclaude.core.conversation.messages import Usage

pytestmark = pytest.mark.unit

ENTRY: dict[str, object] = {
    "type": "cost-state",
    "totalCostUSD": 2.5,
    "totalDuration": 40000,
    "totalAPIDuration": 30000,
    "totalToolDuration": 5000,
    "modelUsage": {
        "claude-sonnet-5-5": {
            "inputTokens": 10,
            "outputTokens": 20,
            "cacheCreationInputTokens": 30,
            "cacheReadInputTokens": 40,
            "costUSD": 2.0,
        },
        "claude-haiku-4-5": {"inputTokens": 1, "costUSD": 0.5},
    },
}


def test_the_cost_the_time_of_work_and_the_models_are_read() -> None:
    state = parse_cost_state(ENTRY, 6)
    assert state is not None
    assert (state.after_messages, state.cost) == (6, 2.5)
    # The time of work is the model and the tools: the waits for the user are in totalDuration only.
    assert state.activity_ms == 35000
    assert state.models["claude-sonnet-5-5"] == ModelTotals(10, 20, 30, 40, 2.0)
    assert state.models["claude-haiku-4-5"] == ModelTotals(1, 0, 0, 0, 0.5)
    assert state.tokens() == Usage(11, 20, 30, 40)


@pytest.mark.parametrize("cost", [None, "free", True])
def test_an_entry_without_a_cost_gives_nothing(cost: object) -> None:
    assert parse_cost_state({"totalCostUSD": cost}, 0) is None


def test_the_missing_or_wrong_parts_count_for_nothing() -> None:
    state = parse_cost_state({"totalCostUSD": 1, "modelUsage": {"m": 3, "n": {"costUSD": "x"}}}, 0)
    assert state == CostState(0, 1.0, 0, {"n": ModelTotals()})


def test_what_came_after_an_earlier_state_is_the_difference_and_never_below_zero() -> None:
    later = parse_cost_state(ENTRY, 6)
    earlier = CostState(
        2, 1.0, 10000, {"claude-sonnet-5-5": ModelTotals(4, 5, 6, 7, 0.75), "gone": ModelTotals()}
    )
    assert later is not None
    own = later.minus(earlier)
    assert (own.cost, own.activity_ms) == (1.5, 25000)
    assert own.models["claude-sonnet-5-5"] == ModelTotals(6, 15, 24, 33, 1.25)
    assert own.models["claude-haiku-4-5"] == ModelTotals(1, 0, 0, 0, 0.5)  # not in the earlier one
    assert earlier.minus(later).cost == 0.0
