"""The presenter of the workspaces, with a fake view: no wx, no window."""

from pathlib import Path

import pytest
from fake_claude_files import FakeClaudeFiles

from wxclaude.core.claude.claude_projects import ClaudeProject
from wxclaude.core.claude.cost_state import CostState, ModelTotals
from wxclaude.core.config.settings import Settings
from wxclaude.core.config.workspaces import workspace_label
from wxclaude.presenters.workspace_presenter import WorkspaceLinks, WorkspacePresenter

pytestmark = pytest.mark.unit


class FakeView:
    """Answers the folder and list questions with what the test set; records the messages."""

    def __init__(self, folder: Path | None = None, index: int | None = None) -> None:
        self.folder = folder
        self.index = index
        self.defaults: list[Path | None] = []
        self.choices: list[list[str]] = []
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def choose_folder(self, default: Path | None) -> Path | None:
        self.defaults.append(default)
        return self.folder

    def choose(self, title: str, prompt: str, labels: list[str]) -> int | None:
        self.choices.append(labels)
        return self.index

    def show_error(self, message: str) -> None:
        self.errors.append(message)

    def show_file_warning(self, details: str) -> None:
        self.warnings.append(details)


class Window:
    """Records what the presenter asks of the window."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def links(self) -> WorkspaceLinks:
        return WorkspaceLinks(
            close_conversation=lambda: self.calls.append("close"),
            select_conversation=lambda folder: self.calls.append(f"select {folder.name}"),
            changed=lambda: self.calls.append("changed"),
            save_settings=lambda: self.calls.append("save"),
        )


def _presenter(
    view: FakeView, settings: Settings | None = None
) -> tuple[WorkspacePresenter, Window]:
    window = Window()
    presenter = WorkspacePresenter(
        view, settings or Settings.load(None), window.links(), FakeClaudeFiles()
    )
    return presenter, window


def _folder(tmp_path: Path, name: str) -> Path:
    folder = tmp_path / name
    folder.mkdir()
    return folder


def test_opening_a_folder_closes_the_conversation_and_selects_one_of_the_new_folder(
    tmp_path: Path,
) -> None:
    work = _folder(tmp_path, "work")
    presenter, window = _presenter(FakeView())
    presenter.open(work)
    assert window.calls == ["close", "changed", "save", "select work"]
    assert presenter.workspace == work
    assert presenter.state is not None


def test_opening_the_same_folder_again_keeps_the_conversation(tmp_path: Path) -> None:
    work = _folder(tmp_path, "work")
    presenter, window = _presenter(FakeView())
    presenter.open(work)
    window.calls.clear()
    presenter.open(work)
    assert window.calls == ["changed", "save"]


def test_the_chosen_folder_is_opened_and_the_current_one_proposed(tmp_path: Path) -> None:
    first, second = _folder(tmp_path, "first"), _folder(tmp_path, "second")
    view = FakeView(folder=first)
    presenter, _window = _presenter(view)
    presenter.choose_folder()
    view.folder = second
    presenter.choose_folder()
    assert view.defaults == [None, first]
    assert presenter.workspace == second


def test_cancelling_the_folder_dialog_opens_nothing() -> None:
    presenter, window = _presenter(FakeView(folder=None))
    presenter.choose_folder()
    assert presenter.workspace is None
    assert window.calls == []


def test_without_any_claude_project_an_error_is_shown() -> None:
    view = FakeView()
    presenter, _window = _presenter(view)
    presenter.choose_project()
    assert view.errors == ["Claude Code has no project yet."]
    assert view.choices == []


def test_a_claude_project_can_be_chosen_and_opened(tmp_path: Path) -> None:
    first, second = _folder(tmp_path, "first"), _folder(tmp_path, "second")
    files = FakeClaudeFiles(projects=[ClaudeProject(first, 2.0), ClaudeProject(second, 1.0)])
    view = FakeView(index=1)
    presenter = WorkspacePresenter(view, Settings.load(None), Window().links(), files)
    presenter.choose_project()
    assert view.choices == [[workspace_label(str(first)), workspace_label(str(second))]]
    assert presenter.workspace == second
    view.index = None  # cancelled: the workspace stays
    presenter.choose_project()
    assert presenter.workspace == second


def _persistent(tmp_path: Path) -> Settings:
    return Settings.load(tmp_path / "config" / "settings.json")


def _states(*totals: float) -> list[CostState]:
    return [
        CostState(2, total, 4000, {"claude-haiku-4-5": ModelTotals(1, 2, 3, 4, total)})
        for total in totals
    ]


def test_the_conversations_that_exist_are_counted_once_at_the_first_use(tmp_path: Path) -> None:
    work = _folder(tmp_path, "work")
    files = FakeClaudeFiles()
    files.add_session(work, "one", "Hello", "Again", cost_states=_states(0.5))
    files.add_session(work, "two", "Hi", cost_states=_states(0.25))
    settings = _persistent(tmp_path)
    view = FakeView()
    presenter = WorkspacePresenter(view, settings, Window().links(), files)
    presenter.open(work)
    stats = presenter.stats
    assert stats is not None
    assert (stats.messages, stats.conversations, stats.cost) == (3, ["two", "one"], 0.75)
    assert stats.includes_past
    assert stats.store is not None
    assert stats.store.exists()
    # Opened again (another start of the application): the file is used, nothing is counted again.
    files.add_session(work, "three", "More", cost_states=_states(9.0))
    again = WorkspacePresenter(FakeView(), settings, Window().links(), files)
    again.open(work)
    assert again.stats is not None
    assert (again.stats.messages, again.stats.cost) == (3, 0.75)


def test_a_workspace_without_conversation_has_empty_statistics_and_no_file(tmp_path: Path) -> None:
    work = _folder(tmp_path, "work")
    presenter = WorkspacePresenter(
        FakeView(), _persistent(tmp_path), Window().links(), FakeClaudeFiles()
    )
    presenter.open(work)
    stats = presenter.stats
    assert stats is not None
    assert (stats.messages, stats.includes_past) == (0, False)
    assert stats.store is not None
    assert not stats.store.exists()


def test_each_workspace_has_its_own_statistics(tmp_path: Path) -> None:
    first, second = _folder(tmp_path, "first"), _folder(tmp_path, "second")
    files = FakeClaudeFiles()
    files.add_session(first, "one", "Hello", cost_states=_states(0.5))
    presenter = WorkspacePresenter(FakeView(), _persistent(tmp_path), Window().links(), files)
    presenter.open(first)
    assert presenter.stats is not None
    assert presenter.stats.messages == 1
    presenter.open(second)
    assert presenter.stats.messages == 0


def test_conversations_that_cannot_be_read_are_left_out_and_said(tmp_path: Path) -> None:
    work = _folder(tmp_path, "work")
    files = FakeClaudeFiles()
    files.add_session(work, "good", "Hello")
    for name in ("bad", "worse"):
        info = files.add_session(work, name, "x")
        del files.contents[info.path]
    view = FakeView()
    presenter = WorkspacePresenter(view, Settings.load(None), Window().links(), files)
    presenter.open(work)
    assert view.errors == ["2 conversations could not be read and are not in the statistics."]
    assert presenter.stats is not None
    assert presenter.stats.messages == 1


def test_a_damaged_ledger_is_reported_and_counted_again_from_the_conversations(
    tmp_path: Path,
) -> None:
    work = _folder(tmp_path, "work")
    files = FakeClaudeFiles()
    files.add_session(work, "one", "Hello", cost_states=_states(0.5))
    settings = _persistent(tmp_path)
    first = WorkspacePresenter(FakeView(), settings, Window().links(), files)
    first.open(work)
    assert first.stats is not None
    assert first.stats.store is not None
    first.stats.store.write_text("{ not json", encoding="utf-8")
    view = FakeView()
    again = WorkspacePresenter(view, settings, Window().links(), files)
    again.open(work)
    assert len(view.warnings) == 1
    assert again.stats is not None
    assert again.stats.messages == 1


def test_a_recent_folder_that_is_gone_is_dropped_and_reported(tmp_path: Path) -> None:
    kept = _folder(tmp_path, "kept")
    gone = tmp_path / "gone"
    settings = Settings.load(None)
    settings.recent_workspaces = [str(gone), str(kept)]
    view = FakeView()
    presenter, _window = _presenter(view, settings)
    presenter.open_recent(str(gone))
    assert settings.recent_workspaces == [str(kept)]
    assert "no longer exists" in view.errors[0]
    assert presenter.workspace is None


def test_the_last_workspace_is_reopened_at_startup_only_if_asked_and_present(
    tmp_path: Path,
) -> None:
    work = _folder(tmp_path, "work")
    settings = Settings.load(None)
    settings.last_workspace = str(work)
    presenter, window = _presenter(FakeView(), settings)
    presenter.restore_last_session()
    assert presenter.workspace == work
    assert window.calls[-1] == "select work"
    settings.reopen_last = False
    other, _window = _presenter(FakeView(), settings)
    other.restore_last_session()
    assert other.workspace is None
