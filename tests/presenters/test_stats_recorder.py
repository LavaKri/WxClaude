"""Adding the finished messages to the statistics of the workspace, with a clock we move by hand."""

from datetime import datetime
from pathlib import Path

import pytest

from wxclaude.core.claude.events import TurnResult
from wxclaude.core.config.workspace_stats import WorkspaceStats
from wxclaude.core.conversation.messages import Usage
from wxclaude.presenters.stats_recorder import StatsRecorder

pytestmark = pytest.mark.unit


class Clock:
    def __init__(self) -> None:
        self.seconds = 0.0

    def __call__(self) -> float:
        return self.seconds


def _result(duration_ms: int | None = 34400) -> TurnResult:
    return TurnResult(False, "success", "", Usage(3, 4, 5, 6), duration_ms, 0.05, 2)


class Setup:
    def __init__(self, stats: WorkspaceStats | None) -> None:
        self.stats = stats
        self.clock = Clock()
        self.errors: list[str] = []
        self.recorder = StatsRecorder(
            lambda: self.stats,
            self.errors.append,
            self.clock,
            lambda: datetime(2026, 10, 23, 12, 0),
        )

    def record(self, result: TurnResult | None = None) -> None:
        self.recorder.record(
            result or _result(), conversation_id="c1", model="claude-opus-5-5", cost=0.05
        )


@pytest.fixture
def setup(tmp_path: Path) -> Setup:
    return Setup(WorkspaceStats(tmp_path / "work"))


def test_a_message_is_counted_with_its_tokens_cost_model_and_day(setup: Setup) -> None:
    setup.recorder.start_message()
    setup.record()
    stats = setup.stats
    assert stats is not None
    assert (stats.messages, stats.started, stats.conversations) == (1, "2026-10-23", ["c1"])
    assert stats.tokens == Usage(3, 4, 5, 6)
    assert (stats.activity_ms, stats.cost) == (34400, 0.05)
    assert stats.models["claude-opus-5-5"].messages == 1


def test_the_time_a_permission_question_stays_open_is_not_time_of_work(setup: Setup) -> None:
    setup.recorder.start_message()
    with setup.recorder.waiting():
        setup.clock.seconds += 30
    with setup.recorder.waiting():  # a second question
        setup.clock.seconds += 2.5
    setup.record(_result(40000))
    assert setup.stats is not None
    assert setup.stats.activity_ms == 7500


def test_the_waits_of_a_message_are_forgotten_by_the_next_one(setup: Setup) -> None:
    setup.recorder.start_message()
    with setup.recorder.waiting():
        setup.clock.seconds += 10
    setup.record(_result(12000))
    setup.recorder.start_message()
    setup.record(_result(5000))
    assert setup.stats is not None
    assert setup.stats.activity_ms == 2000 + 5000


def test_a_question_that_ended_by_an_error_still_counts_as_a_wait(setup: Setup) -> None:
    setup.recorder.start_message()

    def ask_and_fail() -> None:
        with setup.recorder.waiting():
            setup.clock.seconds += 4
            raise RuntimeError("the dialog failed")

    with pytest.raises(RuntimeError):
        ask_and_fail()
    setup.record(_result(10000))
    assert setup.stats is not None
    assert setup.stats.activity_ms == 6000


def test_a_wait_longer_than_the_message_leaves_no_negative_time(setup: Setup) -> None:
    setup.recorder.start_message()
    with setup.recorder.waiting():
        setup.clock.seconds += 60
    setup.record(_result(None))
    assert setup.stats is not None
    assert setup.stats.activity_ms == 0


def test_without_a_workspace_nothing_is_counted_and_nothing_is_said() -> None:
    nothing = Setup(None)
    nothing.recorder.start_message()
    nothing.record()
    assert nothing.errors == []


def test_a_ledger_that_cannot_be_saved_is_reported_once_and_still_counts(tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("a file, not a folder", encoding="utf-8")
    setup = Setup(WorkspaceStats.load(tmp_path / "work", blocker))
    setup.recorder.start_message()
    setup.record()
    setup.record()
    assert len(setup.errors) == 1
    assert setup.errors[0].startswith("The statistics of the workspace could not be saved.")
    assert setup.stats is not None
    assert setup.stats.messages == 2


def test_each_message_is_written_to_the_file(tmp_path: Path) -> None:
    setup = Setup(WorkspaceStats.load(tmp_path / "work", tmp_path / "workspaces"))
    setup.recorder.start_message()
    setup.record()
    again = WorkspaceStats.load(tmp_path / "work", tmp_path / "workspaces")
    assert (again.existed, again.messages) == (True, 1)
