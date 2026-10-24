"""Counting the conversations that exist when the statistics of a workspace start."""

import uuid
from pathlib import Path

import pytest

from wxclaude.core.claude.cost_state import CostState, ModelTotals
from wxclaude.core.claude.session_reader import Session
from wxclaude.core.claude.stats_import import import_sessions
from wxclaude.core.config.workspace_stats import WorkspaceStats
from wxclaude.core.conversation.messages import Message, Role, Usage

pytestmark = pytest.mark.unit

SONNET = "claude-sonnet-5-5"
OPUS = "claude-opus-5-5"


def _id(number: int) -> str:
    return str(uuid.UUID(int=number))


def _exchange(start: int, model: str = SONNET, *, hidden: bool = False) -> list[Message]:
    """A prompt and its answer, with identifiers made from ``start`` (a copy keeps them)."""
    return [
        Message(_id(start), Role.USER, "Hello", hidden=hidden),
        Message(_id(start + 1), Role.ASSISTANT, "Hi", model=model),
    ]


def _state(after: int, cost: float, activity_ms: int = 0, model: str = SONNET) -> CostState:
    totals = ModelTotals(10, 20, 30, 40, cost)
    return CostState(after, cost, activity_ms, {model: totals})


def _session(
    messages: list[Message], states: list[CostState] | None = None, started: str = ""
) -> Session:
    return Session(messages=messages, cost_states=states or [], started=started)


def _import(*sessions: tuple[str, Session]) -> WorkspaceStats:
    stats = WorkspaceStats(Path("work"))
    import_sessions(stats, list(sessions))
    return stats


def test_a_conversation_is_counted_with_what_the_cli_wrote_of_it() -> None:
    session = _session(
        [*_exchange(1), *_exchange(3, OPUS)],
        [_state(2, 0.5, 4000), _state(4, 1.5, 9000)],
        "2026-10-21T08:00:00.000Z",
    )
    stats = _import(("a", session))
    assert (stats.messages, stats.conversations) == (2, ["a"])
    assert stats.tokens == Usage(10, 20, 30, 40)  # the last totals, not the sum of the states
    assert (stats.activity_ms, stats.cost) == (9000, 1.5)
    assert stats.started == "2026-10-21"
    assert stats.includes_past
    assert (stats.models[SONNET].messages, stats.models[OPUS].messages) == (1, 1)
    assert stats.models[SONNET].cost == 1.5  # the cost comes from the models of the totals


def test_a_hidden_prompt_is_not_a_message() -> None:
    stats = _import(("a", _session([*_exchange(1), *_exchange(3, hidden=True)])))
    assert stats.messages == 1


def test_a_conversation_without_totals_counts_its_messages_only() -> None:
    stats = _import(("old", _session(_exchange(1))))
    assert (stats.messages, stats.cost, stats.activity_ms) == (1, 0.0, 0)
    assert stats.models[SONNET].messages == 1


def test_nothing_to_count_is_not_a_conversation_and_not_a_past() -> None:
    stats = _import(("empty", _session([])))
    assert (stats.conversations, stats.messages, stats.includes_past) == ([], 0, False)


def test_a_branch_is_counted_from_where_it_leaves_its_conversation() -> None:
    parent = _session([*_exchange(1), *_exchange(3)], [_state(2, 1.0, 3000), _state(4, 2.0, 6000)])
    # The branch copies the first exchange and goes on; its totals start from the parent's 1.0.
    branch = _session([*_exchange(1), *_exchange(5, OPUS)], [_state(4, 1.3, 3500, OPUS)])
    stats = _import(("parent", parent), ("branch", branch))
    assert stats.messages == 3  # the copied prompt is not counted again
    assert stats.cost == pytest.approx(2.0 + 0.3)
    assert stats.activity_ms == 6000 + 500
    assert stats.conversations == ["parent", "branch"]
    assert stats.models[OPUS].messages == 1


def test_two_branches_of_one_conversation_do_not_take_one_another_away() -> None:
    parent = _session([*_exchange(1), *_exchange(3)], [_state(2, 1.0), _state(4, 2.0)])
    first = _session([*_exchange(1), *_exchange(5)], [_state(4, 1.3)])
    second = _session([*_exchange(1), *_exchange(7)], [_state(4, 1.4)])
    stats = _import(("parent", parent), ("first", first), ("second", second))
    assert stats.cost == pytest.approx(2.0 + 0.3 + 0.4)
    assert stats.messages == 4


def test_the_conversation_a_branch_comes_from_keeps_all_its_totals() -> None:
    parent = _session(_exchange(1), [_state(2, 1.0)])
    branch = _session([*_exchange(1), *_exchange(3)], [_state(4, 1.2)])
    assert _import(("branch", branch), ("parent", parent)).cost == pytest.approx(1.2)


def test_messages_without_an_identifier_of_the_file_are_never_taken_for_a_copy() -> None:
    numbered = [Message("0", Role.USER, "Hello"), Message("1", Role.ASSISTANT, "Hi", model=OPUS)]
    stats = _import(
        ("a", _session(list(numbered), [_state(2, 1.0)])),
        ("b", _session(list(numbered), [_state(2, 1.0)])),
    )
    assert (stats.messages, stats.cost) == (2, 2.0)


def test_the_first_day_is_the_oldest_one() -> None:
    stats = _import(
        ("a", _session(_exchange(1), started="2026-10-22T10:00:00Z")),
        ("b", _session(_exchange(3), started="2026-10-19T10:00:00Z")),
        ("c", _session(_exchange(5))),
    )
    assert stats.started == "2026-10-19"
