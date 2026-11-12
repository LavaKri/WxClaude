"""The tab "Environment variables" of the Workspace settings, with a fake view: no wx."""

import json
from pathlib import Path

import pytest

from wxclaude.core.claude.claude_settings import Source, ToolSettings
from wxclaude.presenters.env_vars_presenter import EnvVarsPresenter

pytestmark = pytest.mark.unit


class FakeView:
    """Records what is shown; answers the value and the warning with what the test set."""

    def __init__(self) -> None:
        self.targets: list[str] = []
        self.target = -1
        self.lines: list[str] = []
        self.selected = -1
        self.explanation = ""
        self.actions: tuple[str, bool, bool, bool] = ("", False, False, False)
        self.value: str | None = None
        self.asked: list[tuple[str, str]] = []
        self.allow_versioned = True
        self.warnings = 0
        self.errors: list[str] = []

    def show_targets(self, labels: list[str], selected: int) -> None:
        self.targets, self.target = labels, selected

    def show_rows(self, lines: list[str], selected: int) -> None:
        self.lines, self.selected = lines, selected

    def show_explanation(self, text: str) -> None:
        self.explanation = text

    def show_actions(self, toggle: str, can_toggle: bool, can_set: bool, can_remove: bool) -> None:
        self.actions = (toggle, can_toggle, can_set, can_remove)

    def ask_value(self, name: str, current: str) -> str | None:
        self.asked.append((name, current))
        return self.value

    def confirm_versioned(self) -> bool:
        self.warnings += 1
        return self.allow_versioned

    def show_error(self, message: str) -> None:
        self.errors.append(message)


def workspace(tmp_path: Path, local: object | None = None, shared: object | None = None) -> Path:
    folder = tmp_path / "work"
    (folder / ".claude").mkdir(parents=True)
    for name, data in (("settings.local.json", local), ("settings.json", shared)):
        if data is not None:
            (folder / ".claude" / name).write_text(json.dumps(data), encoding="utf-8")
    return folder


def page(
    folder: Path, *, local_only: bool = False
) -> tuple[EnvVarsPresenter, FakeView, ToolSettings]:
    settings = ToolSettings.load(folder, folder.parent / "config")
    view = FakeView()
    return EnvVarsPresenter(view, settings, local_only=local_only), view, settings


def row(view: FakeView, name: str) -> int:
    return next(i for i, line in enumerate(view.lines) if line.startswith(name + ","))


def test_the_versioned_file_is_the_default_target_and_both_are_offered(tmp_path: Path) -> None:
    presenter, view, _settings = page(workspace(tmp_path))
    assert presenter.target is Source.SETTINGS
    assert view.targets == ["Settings", "SettingsLocal"]
    assert view.target == 0


def test_with_the_preference_only_the_local_file_is_offered(tmp_path: Path) -> None:
    presenter, view, _settings = page(workspace(tmp_path), local_only=True)
    assert presenter.target is Source.LOCAL
    assert view.targets == ["SettingsLocal"]


def test_the_lines_say_the_state_with_commas_and_mark_what_needs_it(tmp_path: Path) -> None:
    folder = workspace(
        tmp_path,
        local={
            "env": {
                "CLAUDE_CODE_DISABLE_WEB_FETCH": "1",
                "API_TIMEOUT_MS": "60000",
                "MY_TOKEN": "sk-secret",
                "HTTPS_PROXY": "http://proxy:3128",
            }
        },
    )
    presenter, view, _settings = page(folder, local_only=True)
    assert "CLAUDE_CODE_DISABLE_WEB_FETCH, enabled" in view.lines
    assert "API_TIMEOUT_MS, set to 60000" in view.lines
    assert "CLAUDE_CODE_USE_POWERSHELL_TOOL, not set" in view.lines
    assert "CLAUDE_CODE_ENABLE_TELEMETRY, not set, ignored in project files" in view.lines
    assert "MY_TOKEN, value set, sensitive" in view.lines
    assert "HTTPS_PROXY, set to http://proxy:3128, sensitive" in view.lines
    assert "sk-secret" not in " ".join(view.lines)
    presenter.select(row(view, "API_TIMEOUT_MS"))
    assert "milliseconds" in view.explanation


def test_a_variable_the_file_adds_is_listed_without_an_explanation(tmp_path: Path) -> None:
    folder = workspace(tmp_path, local={"env": {"MY_OWN": "x"}})
    presenter, view, _settings = page(folder, local_only=True)
    presenter.select(row(view, "MY_OWN"))
    assert view.explanation == "This variable is not described."
    assert view.actions == ("Enable", False, True, True)  # a value, not a flag


def test_a_variable_a_project_file_does_not_apply_says_so(tmp_path: Path) -> None:
    presenter, view, _settings = page(workspace(tmp_path), local_only=True)
    presenter.select(row(view, "CLAUDE_CODE_ENABLE_TELEMETRY"))
    assert view.explanation.endswith("A project file does not apply this variable.")


def test_a_flag_is_enabled_by_the_value_one_and_disabled_by_leaving_the_file(
    tmp_path: Path,
) -> None:
    presenter, view, settings = page(workspace(tmp_path), local_only=True)
    presenter.select(row(view, "CLAUDE_CODE_DISABLE_WEB_FETCH"))
    assert view.actions == ("Enable", True, True, False)
    presenter.toggle()
    assert settings.files[Source.LOCAL].data == {"env": {"CLAUDE_CODE_DISABLE_WEB_FETCH": "1"}}
    assert "CLAUDE_CODE_DISABLE_WEB_FETCH, enabled" in view.lines
    assert view.actions == ("Disable", True, True, True)
    assert view.selected == row(view, "CLAUDE_CODE_DISABLE_WEB_FETCH")  # the selection stays
    presenter.toggle()
    assert settings.files[Source.LOCAL].data == {"env": {}}
    assert view.actions[0] == "Enable"


def test_a_value_is_asked_with_the_current_one_and_kept(tmp_path: Path) -> None:
    folder = workspace(tmp_path, local={"env": {"API_TIMEOUT_MS": "1000"}})
    presenter, view, settings = page(folder, local_only=True)
    presenter.select(row(view, "API_TIMEOUT_MS"))
    view.value = "90000"
    presenter.set_value()
    assert view.asked == [("API_TIMEOUT_MS", "1000")]
    assert settings.files[Source.LOCAL].data["env"] == {"API_TIMEOUT_MS": "90000"}
    assert "API_TIMEOUT_MS, set to 90000" in view.lines


def test_cancelling_the_value_changes_nothing(tmp_path: Path) -> None:
    presenter, view, settings = page(workspace(tmp_path), local_only=True)
    presenter.select(row(view, "API_TIMEOUT_MS"))
    view.value = None
    presenter.set_value()
    assert not settings.files[Source.LOCAL].changed


def test_a_variable_is_taken_out_of_the_file(tmp_path: Path) -> None:
    folder = workspace(tmp_path, local={"env": {"API_TIMEOUT_MS": "1000", "KEEP": "1"}})
    presenter, view, settings = page(folder, local_only=True)
    presenter.select(row(view, "API_TIMEOUT_MS"))
    presenter.remove()
    assert settings.files[Source.LOCAL].data["env"] == {"KEEP": "1"}
    assert "API_TIMEOUT_MS, not set" in view.lines


def test_nothing_is_selected_so_the_buttons_are_greyed(tmp_path: Path) -> None:
    presenter, view, settings = page(workspace(tmp_path), local_only=True)
    presenter.select(-1)
    assert view.actions == ("Enable", False, False, False)
    assert view.explanation == ""
    presenter.toggle()
    presenter.set_value()
    presenter.remove()
    assert not settings.files[Source.LOCAL].changed


def test_changing_the_versioned_file_asks_once_and_a_refusal_changes_nothing(
    tmp_path: Path,
) -> None:
    presenter, view, settings = page(workspace(tmp_path))
    presenter.select(row(view, "CLAUDE_CODE_DISABLE_WEB_FETCH"))
    view.allow_versioned = False
    presenter.toggle()
    assert view.warnings == 1
    assert not settings.files[Source.SETTINGS].changed
    view.allow_versioned = True
    presenter.toggle()
    presenter.toggle()
    assert view.warnings == 2  # asked again after the refusal, then once for the two changes
    assert settings.files[Source.SETTINGS].changed


def test_the_local_file_is_changed_without_a_warning(tmp_path: Path) -> None:
    presenter, view, _settings = page(workspace(tmp_path))
    presenter.select_target(1)
    assert presenter.target is Source.LOCAL
    presenter.select(row(view, "CLAUDE_CODE_DISABLE_WEB_FETCH"))
    presenter.toggle()
    assert view.warnings == 0


def test_the_other_file_is_shown_when_the_target_changes(tmp_path: Path) -> None:
    folder = workspace(
        tmp_path,
        local={"env": {"API_TIMEOUT_MS": "1"}},
        shared={"env": {"API_TIMEOUT_MS": "2"}},
    )
    presenter, view, _settings = page(folder)
    assert "API_TIMEOUT_MS, set to 2" in view.lines
    presenter.select_target(1)
    assert "API_TIMEOUT_MS, set to 1" in view.lines
    presenter.select_target(7)  # out of range: nothing happens
    assert presenter.target is Source.LOCAL


def test_a_file_that_cannot_be_changed_is_reported(tmp_path: Path) -> None:
    folder = workspace(tmp_path)
    (folder / ".claude" / "settings.local.json").write_text("{not json", encoding="utf-8")
    presenter, view, _settings = page(folder, local_only=True)
    presenter.select(row(view, "API_TIMEOUT_MS"))
    view.value = "1"
    presenter.set_value()
    assert len(view.errors) == 1
    assert "settings.local.json" in view.errors[0]
