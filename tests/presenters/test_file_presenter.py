"""The presenter of the files and the desktop, with a fake view: no wx, no window."""

from pathlib import Path

import pytest

from wxclaude.core.errors import HelpError
from wxclaude.presenters.file_presenter import FilePresenter

pytestmark = pytest.mark.unit


class FakeView:
    """Answers the export dialog with ``path``; the desktop accepts unless told otherwise."""

    def __init__(self, path: Path | None = None, *, desktop_works: bool = True) -> None:
        self.path = path
        self.desktop_works = desktop_works
        self.opened: list[Path] = []
        self.abouts: list[str] = []
        self.errors: list[str] = []

    def ask_export_path(self) -> Path | None:
        return self.path

    def open_folder(self, folder: Path) -> bool:
        self.opened.append(folder)
        return self.desktop_works

    def open_file(self, path: Path) -> bool:
        self.opened.append(path)
        return self.desktop_works

    def show_about(self, message: str) -> None:
        self.abouts.append(message)

    def show_error(self, message: str) -> None:
        self.errors.append(message)


def test_the_conversation_is_exported_to_the_chosen_file(tmp_path: Path) -> None:
    target = tmp_path / "out.md"
    FilePresenter(FakeView(target)).export("# Hello")
    assert target.read_text(encoding="utf-8").startswith("# Hello")


def test_a_cancelled_export_says_nothing() -> None:
    view = FakeView(None)
    FilePresenter(view).export("text")
    assert view.errors == []


def test_a_folder_that_is_gone_or_refused_is_reported(tmp_path: Path) -> None:
    view = FakeView(desktop_works=False)
    presenter = FilePresenter(view)
    presenter.open_folder(tmp_path / "gone")
    presenter.open_folder(tmp_path)
    presenter.open_folder(None)
    assert view.opened == [tmp_path]
    assert len(view.errors) == 2
    assert "no longer exists" in view.errors[0]
    assert "cannot be opened" in view.errors[1]


def test_the_help_page_of_the_language_is_opened(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    page = tmp_path / "fr.html"
    monkeypatch.setattr("wxclaude.presenters.file_presenter.help_page", lambda language: page)
    view = FakeView()
    FilePresenter(view).show_help("fr")
    assert view.opened == [page]


def test_a_missing_help_page_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(language: str) -> Path:
        raise HelpError("The help page is missing.")

    monkeypatch.setattr("wxclaude.presenters.file_presenter.help_page", missing)
    view = FakeView()
    FilePresenter(view).show_help("fr")
    assert view.opened == []
    assert view.errors == ["The help page cannot be opened.\nThe help page is missing."]


def test_about_gives_the_version() -> None:
    view = FakeView()
    FilePresenter(view).about()
    assert view.abouts[0].startswith("WxClaude ")
