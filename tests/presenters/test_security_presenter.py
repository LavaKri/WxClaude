"""The trust state of a workspace, with a fake view: no wx, no window."""

import json
from pathlib import Path

import pytest
from fake_security_view import FakeView

from wxclaude.core.config.workspace_state import WorkspaceState
from wxclaude.core.security.watch import ExternalChangeError, FileState, FileStatus
from wxclaude.core.speech.announcements import Announce
from wxclaude.presenters.security_presenter import (
    AlertChoice,
    ApprovalChoice,
    SecurityPresenter,
)

pytestmark = pytest.mark.unit

SETTINGS = ".claude/settings.json"


class Setup:
    """A workspace on disk, its state kept in a folder of the test, and a presenter."""

    def __init__(self, tmp_path: Path, view: FakeView) -> None:
        self.workspace = tmp_path / "work"
        (self.workspace / ".claude").mkdir(parents=True)
        self.directory = tmp_path / "data"
        self.view = view
        self.presenter = SecurityPresenter(view)
        self.state = self.open()

    def open(self) -> WorkspaceState:
        state = WorkspaceState.load(self.workspace, self.directory)
        self.presenter.open(self.workspace, state)
        return state

    def write(self, relative: str, text: str) -> Path:
        path = self.workspace / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path


def setup(tmp_path: Path, view: FakeView | None = None) -> Setup:
    return Setup(tmp_path, view or FakeView())


# -- a folder never seen ----------------------------------------------------------------------


def test_a_folder_is_restricted_until_the_user_decides(tmp_path: Path) -> None:
    work = setup(tmp_path)
    assert work.presenter.restricted
    assert not work.state.trusted


def test_nothing_is_shown_before_the_window_greets(tmp_path: Path) -> None:
    work = setup(tmp_path)
    assert work.view.offers == []
    assert work.view.said == []


def test_a_new_folder_is_offered_the_approval_with_the_files_it_holds(tmp_path: Path) -> None:
    work = setup(tmp_path)
    work.write(SETTINGS, "{}")
    work.write(".claude/agents/review.md", "agent")
    work.presenter.greet()
    ((folder, used_before, files),) = work.view.offers
    assert folder == work.workspace
    assert not used_before
    assert files == [".claude/agents/review.md", SETTINGS]


def test_approving_makes_the_folder_trusted_and_records_the_files(tmp_path: Path) -> None:
    work = setup(tmp_path, FakeView(approval=ApprovalChoice.APPROVE))
    work.write(SETTINGS, "{}")
    work.presenter.greet()
    assert not work.presenter.restricted
    assert work.view.announces == [Announce.FOLDER_APPROVED]
    reloaded = work.open()
    assert reloaded.trusted
    assert reloaded.approval_asked
    assert SETTINGS in reloaded.watch
    assert work.view.errors == []


def test_keeping_it_restricted_is_remembered_and_the_user_is_not_asked_again(
    tmp_path: Path,
) -> None:
    work = setup(tmp_path, FakeView(approval=ApprovalChoice.KEEP_RESTRICTED))
    work.presenter.greet()
    assert work.presenter.restricted
    assert work.view.announces == [Announce.FOLDER_RESTRICTED]
    work.open()
    work.presenter.greet()
    assert len(work.view.offers) == 1  # not asked a second time
    assert work.view.announces == [Announce.FOLDER_RESTRICTED] * 2  # the state is said


def test_a_workspace_used_before_is_said_to_be(tmp_path: Path) -> None:
    work = setup(tmp_path)
    work.state.save()  # the file of the workspace exists from now on
    work.open()
    work.presenter.greet()
    assert work.view.offers[0][1] is True


def test_a_state_that_cannot_be_recorded_leaves_the_folder_restricted(tmp_path: Path) -> None:
    work = setup(tmp_path, FakeView(approval=ApprovalChoice.APPROVE))
    work.write(SETTINGS, "{}")
    work.directory.parent.joinpath("data").write_text("a file, not a folder", encoding="utf-8")
    work.presenter.greet()
    assert work.presenter.restricted
    assert len(work.view.errors) == 1
    assert Announce.FOLDER_APPROVED not in work.view.announces


# -- an approved folder ---------------------------------------------------------------------


def approved(tmp_path: Path, alert: AlertChoice | None = None) -> Setup:
    """A folder the user approved; the alert, if any, will be answered with ``alert``."""
    work = setup(tmp_path, FakeView(approval=ApprovalChoice.APPROVE))
    work.write(SETTINGS, "{}")
    work.presenter.greet()
    work.view.said.clear()
    work.view.offers.clear()
    work.view.alert = alert
    work.state = work.open()
    return work


def test_an_approved_folder_is_greeted_without_a_word_when_nothing_changed(
    tmp_path: Path,
) -> None:
    work = approved(tmp_path)
    work.presenter.greet()
    assert work.view.said == []
    assert work.view.alerts == []
    assert not work.presenter.restricted


def test_a_change_is_shown_with_its_differences(tmp_path: Path) -> None:
    work = approved(tmp_path)
    work.write(SETTINGS, json.dumps({"hooks": {"Stop": []}}))
    work.presenter.greet()
    (spec,) = work.view.alerts
    assert spec.lines == [f"{SETTINGS}, changed"]
    assert spec.details is not None
    assert '+  "hooks"' in spec.details[0]
    assert "-" in spec.details[0]


def test_a_secret_that_changed_is_never_shown_in_the_differences(tmp_path: Path) -> None:
    work = setup(tmp_path, FakeView(approval=ApprovalChoice.APPROVE))
    work.write(SETTINGS, json.dumps({"env": {"MY_TOKEN": "sk-old"}}))
    work.presenter.greet()
    work.state = work.open()
    work.write(SETTINGS, json.dumps({"env": {"MY_TOKEN": "sk-new"}}))
    work.presenter.greet()
    (spec,) = work.view.alerts
    assert spec.details is not None
    assert "sk-old" not in spec.details[0]
    assert "sk-new" not in spec.details[0]


def test_a_file_that_appears_is_shown_as_added_lines(tmp_path: Path) -> None:
    work = approved(tmp_path)
    work.write(".mcp.json", json.dumps({"mcpServers": {"x": {"command": "run"}}}))
    work.presenter.greet()
    (spec,) = work.view.alerts
    assert spec.lines == [".mcp.json, added"]
    assert spec.details is not None
    assert '+  "mcpServers"' in spec.details[0]


def test_a_file_that_disappears_is_shown_as_removed_lines(tmp_path: Path) -> None:
    work = approved(tmp_path)
    (work.workspace / SETTINGS).unlink()
    work.presenter.greet()
    (spec,) = work.view.alerts
    assert spec.lines == [f"{SETTINGS}, removed"]


def test_without_a_copy_the_details_say_so(tmp_path: Path) -> None:
    work = setup(tmp_path, FakeView(approval=ApprovalChoice.APPROVE))
    work.write(SETTINGS, '{"broken": ')  # cannot be masked, so no copy was kept
    work.presenter.greet()
    work.state = work.open()
    work.write(SETTINGS, '{"broken": 1')
    work.presenter.greet()
    (spec,) = work.view.alerts
    assert spec.details == ["No details are available for this file."]


def test_accepting_the_changes_makes_them_the_reference(tmp_path: Path) -> None:
    work = approved(tmp_path, AlertChoice.ACCEPT)
    work.write(SETTINGS, '{"a": 1}')
    work.presenter.greet()
    assert len(work.view.alerts) == 1
    work.open()
    work.presenter.greet()
    assert len(work.view.alerts) == 1  # no second alert
    assert not work.presenter.restricted


def test_restricting_from_the_alert_takes_the_approval_back(tmp_path: Path) -> None:
    work = approved(tmp_path, AlertChoice.RESTRICT)
    work.write(SETTINGS, '{"a": 1}')
    work.presenter.greet()
    assert work.presenter.restricted
    assert work.view.announces == [Announce.FOLDER_RESTRICTED]
    reloaded = work.open()
    assert not reloaded.trusted
    assert SETTINGS in reloaded.watch  # what was approved is kept for a later approval


def test_a_restricted_folder_is_not_alerted_about_changes(tmp_path: Path) -> None:
    work = approved(tmp_path, AlertChoice.RESTRICT)
    work.write(SETTINGS, '{"a": 1}')
    work.presenter.greet()
    work.view.alerts.clear()
    work.view.said.clear()
    work.open()
    work.presenter.greet()
    assert work.view.alerts == []
    assert work.view.announces == [Announce.FOLDER_RESTRICTED]


def test_deciding_nothing_about_a_change_says_it_and_asks_again_next_time(tmp_path: Path) -> None:
    work = approved(tmp_path)
    work.write(SETTINGS, '{"a": 1}')
    work.presenter.greet()
    assert work.view.said == [(Announce.FOLDER_CHANGED, {"files": SETTINGS})]
    assert not work.presenter.restricted
    work.open()
    work.presenter.greet()
    assert len(work.view.alerts) == 2


def test_restricting_by_hand_and_approving_again(tmp_path: Path) -> None:
    work = approved(tmp_path)
    work.presenter.restrict()
    assert work.presenter.restricted
    work.write(SETTINGS, '{"a": 1}')  # examined by the user meanwhile
    assert work.presenter.approve()
    assert not work.presenter.restricted
    work.open()
    work.presenter.greet()
    assert work.view.alerts == []  # the new content is the reference


# -- the one door for the settings files ----------------------------------------------------


def test_the_guard_is_the_door_of_the_workspace(tmp_path: Path) -> None:
    work = approved(tmp_path)
    assert work.presenter.guard is not None
    work.presenter.guard.write_json(work.workspace / SETTINGS, {"a": 1})
    work.presenter.check()
    assert work.view.alerts == []  # its own write is no change


def test_a_write_refused_for_a_change_from_outside_goes_through_the_alert(tmp_path: Path) -> None:
    work = approved(tmp_path, AlertChoice.ACCEPT)
    work.write(SETTINGS, '{"outside": 1}')
    error = ExternalChangeError([FileStatus(SETTINGS, FileState.CHANGED, True)])
    work.presenter.refused(error)
    (spec,) = work.view.alerts
    assert spec.lines == [f"{SETTINGS}, changed"]
    work.presenter.check()
    assert len(work.view.alerts) == 1  # accepted


def test_check_does_nothing_for_a_restricted_folder_or_without_a_workspace(
    tmp_path: Path,
) -> None:
    SecurityPresenter(FakeView()).check()
    work = setup(tmp_path)
    work.presenter.check()
    assert work.view.alerts == []
    assert SecurityPresenter(FakeView()).guard is None
    assert not SecurityPresenter(FakeView()).restricted


def test_a_state_that_cannot_be_saved_is_reported_when_restricting(tmp_path: Path) -> None:
    work = approved(tmp_path)

    assert work.state.store is not None
    # A folder where the temporary file must be written: the write fails.
    work.state.store.with_name(work.state.store.name + ".tmp").mkdir()
    work.presenter.restrict()
    assert work.presenter.restricted
    assert len(work.view.errors) == 1
