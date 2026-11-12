"""The tab "Security" of the Workspace settings, with a fake view: no wx."""

from pathlib import Path

import pytest
from fake_security_view import FakeView as SecurityView

from wxclaude.core.config.workspace_state import WorkspaceState
from wxclaude.presenters.security_presenter import ApprovalChoice, SecurityPresenter
from wxclaude.presenters.security_tab_presenter import SecurityTabPresenter

pytestmark = pytest.mark.unit

SETTINGS = ".claude/settings.json"


class FakeView:
    """Records what is shown; answers the file chooser with what the test set."""

    def __init__(self) -> None:
        self.trusted = False
        self.max_turns = 0
        self.lines: list[str] = []
        self.watched: list[bool] = []
        self.selected = -1
        self.explanation = ""
        self.actions = (False, False)
        self.chosen: Path | None = None
        self.sure = True
        self.confirmations = 0
        self.errors: list[str] = []

    def show_trusted(self, trusted: bool) -> None:
        self.trusted = trusted

    def show_max_turns(self, turns: int) -> None:
        self.max_turns = turns

    def show_files(self, lines: list[str], watched: list[bool], selected: int) -> None:
        self.lines, self.watched, self.selected = lines, watched, selected

    def show_explanation(self, text: str) -> None:
        self.explanation = text

    def show_actions(self, can_accept: bool, can_forget: bool) -> None:
        self.actions = (can_accept, can_forget)

    def confirm_approval(self) -> bool:
        self.confirmations += 1
        return self.sure

    def ask_file(self, folder: Path) -> Path | None:
        return self.chosen

    def show_error(self, message: str) -> None:
        self.errors.append(message)


class Setup:
    def __init__(self, tmp_path: Path) -> None:
        self.workspace = tmp_path / "work"
        (self.workspace / ".claude").mkdir(parents=True)
        self.security = SecurityPresenter(SecurityView(approval=ApprovalChoice.KEEP_RESTRICTED))
        self.security.open(self.workspace, WorkspaceState.load(self.workspace, tmp_path / "data"))
        self.security.greet()
        self.view = FakeView()
        self.tab = SecurityTabPresenter(self.view, self.security, self.workspace)

    def write(self, relative: str, text: str = "{}") -> Path:
        path = self.workspace / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def index(self, path: str) -> int:
        return next(i for i, line in enumerate(self.view.lines) if line.startswith(path + ","))


def test_the_tab_shows_a_restricted_folder_and_its_watched_files(tmp_path: Path) -> None:
    work = Setup(tmp_path)
    work.write(SETTINGS)
    work.tab.refresh()
    assert not work.view.trusted
    assert f"{SETTINGS}, added" in work.view.lines  # nothing was approved yet
    assert ".claude/settings.local.json, absent" in work.view.lines
    assert all(work.view.watched)
    assert "Restricted folder" in work.view.explanation
    assert "trust" in work.view.explanation


def test_approving_from_the_tab_makes_the_files_the_reference(tmp_path: Path) -> None:
    work = Setup(tmp_path)
    work.write(SETTINGS)
    work.tab.set_trusted(True)
    assert work.view.trusted
    assert not work.security.restricted
    assert f"{SETTINGS}, unchanged" in work.view.lines
    assert work.view.errors == []


def test_restricting_from_the_tab(tmp_path: Path) -> None:
    work = Setup(tmp_path)
    work.tab.set_trusted(True)
    work.tab.set_trusted(False)
    assert not work.view.trusted
    assert work.security.restricted


def test_the_limit_of_turns_is_remembered_with_the_workspace(tmp_path: Path) -> None:
    work = Setup(tmp_path)
    assert work.view.max_turns == 0
    work.tab.set_max_turns(5)
    reloaded = WorkspaceState.load(work.workspace, tmp_path / "data")
    assert reloaded.max_turns == 5
    work.tab.set_max_turns(0)
    assert WorkspaceState.load(work.workspace, tmp_path / "data").max_turns == 0


def test_a_changed_file_can_be_accepted_and_only_it_can(tmp_path: Path) -> None:
    work = Setup(tmp_path)
    work.write(SETTINGS)
    work.tab.set_trusted(True)
    work.write(SETTINGS, '{"a": 1}')
    work.tab.refresh()
    work.tab.select(work.index(SETTINGS))
    assert work.view.actions == (True, False)
    work.tab.accept()
    assert f"{SETTINGS}, unchanged" in work.view.lines
    assert work.view.actions == (False, False)


def test_a_file_that_is_not_changed_cannot_be_accepted(tmp_path: Path) -> None:
    work = Setup(tmp_path)
    work.write(SETTINGS)
    work.tab.set_trusted(True)
    work.tab.select(work.index(SETTINGS))
    assert work.view.actions == (False, False)
    work.tab.accept()
    assert work.view.errors == []


def test_a_file_is_watched_or_not_by_its_check_box(tmp_path: Path) -> None:
    work = Setup(tmp_path)
    work.write(SETTINGS)
    work.tab.set_trusted(True)
    index = work.index(SETTINGS)
    work.tab.set_watched(index, False)
    assert work.view.watched[index] is False
    assert f"{SETTINGS}, unchanged, not watched" in work.view.lines
    work.tab.set_watched(index, True)
    assert work.view.watched[index] is True
    work.tab.set_watched(99, True)  # out of range: nothing happens
    assert work.view.errors == []


def test_a_file_of_the_workspace_can_be_added_then_removed(tmp_path: Path) -> None:
    work = Setup(tmp_path)
    work.tab.set_trusted(True)
    tool = work.write("tools/run.cmd", "echo 1")
    work.view.chosen = tool
    work.tab.add_file()
    assert "tools/run.cmd, unchanged" in work.view.lines
    work.tab.select(work.index("tools/run.cmd"))
    assert work.view.actions == (False, True)
    work.tab.forget()
    assert not any(line.startswith("tools/run.cmd,") for line in work.view.lines)


def test_a_file_outside_the_workspace_is_refused(tmp_path: Path) -> None:
    work = Setup(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("x", encoding="utf-8")
    work.view.chosen = outside
    work.tab.add_file()
    assert len(work.view.errors) == 1
    assert "inside the workspace" in work.view.errors[0]
    work.view.chosen = None
    work.tab.add_file()  # cancelled
    assert len(work.view.errors) == 1


def test_a_default_file_cannot_be_taken_out_of_the_list(tmp_path: Path) -> None:
    work = Setup(tmp_path)
    work.write(SETTINGS)
    work.tab.set_trusted(True)
    work.tab.select(work.index(SETTINGS))
    work.tab.forget()
    assert f"{SETTINGS}, unchanged" in work.view.lines


def test_approving_is_confirmed_first_and_a_refusal_leaves_the_folder_restricted(
    tmp_path: Path,
) -> None:
    work = Setup(tmp_path)
    work.view.sure = False
    work.tab.set_trusted(True)
    assert work.view.confirmations == 1
    assert not work.view.trusted  # the check box goes back
    assert work.security.restricted
    work.view.sure = True
    work.tab.set_trusted(True)
    assert work.view.trusted
