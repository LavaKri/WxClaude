"""The statistics of a workspace: counting, keeping in a file, and the lines that show them."""

import json
from pathlib import Path

import pytest

from wxclaude.core.config.workspace_stats import (
    CountedMessage,
    ModelShare,
    WorkspaceStats,
    format_duration,
    model_family,
    stats_file_name,
)
from wxclaude.core.conversation.messages import Usage
from wxclaude.core.errors import JsonStoreError

pytestmark = pytest.mark.unit

SONNET = "claude-sonnet-5-5"
OPUS = "claude-opus-5-5"


USAGE = Usage(3, 4, 5, 6)


def _message(
    conversation_id: str = "c1",
    usage: Usage | None = USAGE,
    activity_ms: int = 1500,
    cost: float | None = 0.25,
    model: str = SONNET,
) -> CountedMessage:
    return CountedMessage(conversation_id, usage, activity_ms, cost, model, "2026-10-23")


def test_a_message_adds_everything_it_used() -> None:
    stats = WorkspaceStats(Path("work"))
    stats.record_message(_message())
    stats.record_message(_message("c2", Usage(1, 1, 1, 1), 500, None, OPUS))
    stats.record_message(_message("c1"))
    assert (stats.messages, stats.conversations, stats.started) == (3, ["c1", "c2"], "2026-10-23")
    assert stats.tokens == Usage(7, 9, 11, 13)
    assert (stats.activity_ms, stats.cost) == (3500, 0.5)
    assert stats.models == {SONNET: ModelShare(2, 0.5), OPUS: ModelShare(1, 0.0)}


def test_a_message_without_tokens_cost_or_model_counts_what_it_can() -> None:
    stats = WorkspaceStats(Path("work"))
    stats.record_message(_message(usage=None, cost=None, model="", activity_ms=-5))
    assert (stats.messages, stats.tokens, stats.cost, stats.activity_ms) == (1, Usage(), 0.0, 0)
    assert stats.models == {}


def test_the_ledger_is_kept_in_a_file_and_read_again(tmp_path: Path) -> None:
    work = tmp_path / "work"
    stats = WorkspaceStats.load(work, tmp_path / "workspaces")
    assert not stats.existed
    stats.record_message(_message())
    stats.includes_past = True
    stats.save()
    again = WorkspaceStats.load(work, tmp_path / "workspaces")
    assert again.existed
    assert again.lines() == stats.lines()
    assert again.conversations == ["c1"]
    assert again.includes_past
    assert stats.store is not None
    assert stats.store.name == stats_file_name(work)
    assert stats_file_name(work).endswith(".stats.json")


def test_without_a_folder_the_ledger_stays_in_memory(tmp_path: Path) -> None:
    stats = WorkspaceStats.load(tmp_path, None)
    stats.record_message(_message())
    stats.save()
    assert list(tmp_path.iterdir()) == []


def test_the_file_of_another_workspace_is_not_used(tmp_path: Path) -> None:
    work = tmp_path / "work"
    stats = WorkspaceStats.load(work, tmp_path)
    stats.record_message(_message())
    stats.save()
    assert stats.store is not None
    data = json.loads(stats.store.read_text(encoding="utf-8"))
    data["workspace"] = str(tmp_path / "somewhere else")
    stats.store.write_text(json.dumps(data), encoding="utf-8")
    loaded = WorkspaceStats.load(work, tmp_path)
    assert (loaded.messages, loaded.existed) == (0, False)
    assert "another workspace" in loaded.warning


def test_a_damaged_file_gives_empty_statistics_and_a_warning(tmp_path: Path) -> None:
    work = tmp_path / "work"
    store = tmp_path / stats_file_name(work)
    store.write_text("{ not json", encoding="utf-8")
    loaded = WorkspaceStats.load(work, tmp_path)
    assert (loaded.messages, loaded.existed) == (0, False)
    assert loaded.warning


def test_wrong_values_in_the_file_count_for_nothing(tmp_path: Path) -> None:
    work = tmp_path / "work"
    store = tmp_path / stats_file_name(work)
    bad = {
        "workspace": str(work),
        "messages": -3,
        "conversations": ["a", 4],
        "tokens": {"input": "many", "output": 7},
        "cost": True,
        "models": {"m": {"messages": 2, "cost": -1}, "n": 5},
    }
    store.write_text(json.dumps(bad), encoding="utf-8")
    loaded = WorkspaceStats.load(work, tmp_path)
    assert (loaded.messages, loaded.cost, loaded.conversations) == (0, 0.0, ["a"])
    assert loaded.tokens == Usage(0, 7, 0, 0)
    assert loaded.models == {"m": ModelShare(2, 0.0)}


def test_a_ledger_that_cannot_be_written_raises(tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("a file, not a folder", encoding="utf-8")
    stats = WorkspaceStats.load(tmp_path / "work", blocker)
    with pytest.raises(JsonStoreError):
        stats.save()


@pytest.mark.parametrize(
    ("milliseconds", "text"),
    [
        (0, "0 s"),
        (59_400, "59 s"),
        (60_000, "1 min"),
        (3_599_000, "59 min"),
        (3_600_000, "1 h 00"),
        (7_800_000, "2 h 10"),
        (36_900_000, "10 h 15"),
    ],
)
def test_a_duration_uses_its_largest_unit(milliseconds: int, text: str) -> None:
    assert format_duration(milliseconds) == text


@pytest.mark.parametrize(
    ("model", "family"),
    [
        ("claude-opus-5-5", "Opus"),
        ("claude-haiku-4-5-20251001", "Haiku"),
        ("Claude-Sonnet-5-5", "Sonnet"),
        ("claude-fable-5-1", "Fable"),
        ("some-other-model", "some-other-model"),
    ],
)
def test_a_model_is_named_by_its_family(model: str, family: str) -> None:
    assert model_family(model) == family


def _full() -> WorkspaceStats:
    return WorkspaceStats(
        Path("work"),
        started="2026-10-23",
        messages=100,
        conversations=["a", "b", "c"],
        tokens=Usage(4000, 5000, 1000, 800000),
        activity_ms=(2 * 3600 + 10 * 60) * 1000,
        cost=3.0,
        models={SONNET: ModelShare(50, 2.1), OPUS: ModelShare(50, 0.9)},
    )


def test_the_statistics_are_shown_one_fact_per_line() -> None:
    assert _full().lines() == [
        "Global statistics of the workspace",
        "Started on 2026-10-23",
        "100 messages, in 3 conversations",
        "Tokens exchanged: 10000, read from the cache: 800000",
        "2 h 10 of activity (model time + tool time)",
        "Cost: 3.00 dollars at list price",
        "Cost split: 70 % Sonnet, 30 % Opus",
        "Messages split: 50 % Opus, 50 % Sonnet",
    ]


def test_big_numbers_of_tokens_are_written_short() -> None:
    stats = _full()
    stats.tokens = Usage(4_000_000, 5_000_000, 3_000_000, 721_582_690)
    assert "Tokens exchanged: 12 million, read from the cache: 722 million" in stats.lines()


def test_the_versions_of_a_family_are_added_in_the_split() -> None:
    stats = _full()
    stats.models = {
        "claude-haiku-4-5": ModelShare(1, 0.1),
        "claude-haiku-4-5-20251001": ModelShare(2, 0.2),
        OPUS: ModelShare(1, 0.7),
    }
    lines = stats.lines()
    assert "Cost split: 70 % Opus, 30 % Haiku" in lines
    assert "Messages split: 75 % Haiku, 25 % Opus" in lines


def test_a_share_that_rounds_to_nothing_is_still_mentioned() -> None:
    stats = _full()
    stats.models = {OPUS: ModelShare(500, 99.7), "claude-haiku-4-5": ModelShare(1, 0.3)}
    assert "Cost split: 100 % Opus, less than 1 % Haiku" in stats.lines()


def test_one_message_in_one_conversation_and_a_small_cost() -> None:
    stats = WorkspaceStats(Path("work"))
    stats.record_message(_message(cost=0.0042, activity_ms=90_000))
    lines = stats.lines()
    assert "1 message, in 1 conversation" in lines
    assert "Cost: 0.0042 dollars at list price" in lines
    assert "1 min of activity (model time + tool time)" in lines
    assert "Cost split: 100 % Sonnet" in lines


def test_what_has_no_value_is_left_out() -> None:
    stats = WorkspaceStats(Path("work"))
    stats.record_message(_message(cost=None, model=""))
    lines = stats.lines()
    assert not any(line.startswith(("Cost", "Messages split")) for line in lines)


def test_nothing_is_counted_yet() -> None:
    assert WorkspaceStats(Path("work")).lines() == [
        "Global statistics of the workspace",
        "No message counted yet.",
    ]


def test_the_past_that_was_counted_is_said() -> None:
    stats = _full()
    stats.includes_past = True
    assert "deleted before are not" in stats.lines()[-1]
