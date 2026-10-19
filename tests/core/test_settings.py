import json
from pathlib import Path

import pytest

from wxclaude.core.agents import Agent
from wxclaude.core.errors import SettingsError
from wxclaude.core.screen_reader import default_output
from wxclaude.core.settings import Settings
from wxclaude.core.shortcuts import INTERRUPT_COMMAND, NEW_CONVERSATION_COMMAND

pytestmark = pytest.mark.unit


def test_defaults_when_file_is_missing(tmp_path: Path) -> None:
    settings = Settings.load(tmp_path / "settings.json")
    assert settings.language == "fr"
    assert settings.alternative_agent == Agent(effort="low")
    assert settings.recent_workspaces == []


def test_save_then_load_round_trip(tmp_path: Path) -> None:
    store = tmp_path / "settings.json"
    settings = Settings.load(store)
    settings.language = "en"
    settings.default_agent = Agent(model="sonnet")
    settings.alternative_agent = Agent(model="haiku", permission_mode="plan")
    settings.recent_workspaces = ["C:\\work\\one"]
    settings.save()
    loaded = Settings.load(store)
    assert loaded.language == "en"
    assert loaded.default_agent == Agent(model="sonnet")
    assert loaded.alternative_agent == Agent(model="haiku", permission_mode="plan")
    assert loaded.recent_workspaces == ["C:\\work\\one"]


def test_shortcuts_store_only_the_differences_from_the_default(tmp_path: Path) -> None:
    store = tmp_path / "settings.json"
    settings = Settings.load(store)
    settings.set_shortcut(INTERRUPT_COMMAND, "Ctrl+K")
    settings.set_shortcut(NEW_CONVERSATION_COMMAND, NEW_CONVERSATION_COMMAND.default)
    assert settings.shortcuts == {INTERRUPT_COMMAND.id: "Ctrl+K"}
    settings.save()
    loaded = Settings.load(store)
    assert loaded.shortcut_for(INTERRUPT_COMMAND) == "Ctrl+K"
    assert loaded.shortcut_for(NEW_CONVERSATION_COMMAND) == "Ctrl+N"


def test_invalid_or_conflicting_saved_shortcuts_are_ignored(tmp_path: Path) -> None:
    store = tmp_path / "settings.json"
    saved = {INTERRUPT_COMMAND.id: "Ctrl+N", NEW_CONVERSATION_COMMAND.id: "nonsense+"}
    store.write_text(json.dumps({"shortcuts": saved}), encoding="utf-8")
    loaded = Settings.load(store)
    assert loaded.shortcut_for(INTERRUPT_COMMAND) == INTERRUPT_COMMAND.default
    assert loaded.shortcut_for(NEW_CONVERSATION_COMMAND) == "Ctrl+N"


def test_the_application_starts_with_the_agents_chosen_by_the_user(tmp_path: Path) -> None:
    settings = Settings.load(tmp_path / "settings.json")
    assert settings.default_agent == Agent(
        model="sonnet", effort="medium", permission_mode="manual"
    )
    assert settings.alternative_agent == Agent(effort="low")


def test_screen_reader_output_round_trip_and_unknown_value(tmp_path: Path) -> None:
    store = tmp_path / "settings.json"
    settings = Settings.load(store)
    settings.screen_reader_output = "none"
    settings.save()
    assert Settings.load(store).screen_reader_output == "none"
    store.write_text('{"screen_reader_output": "carrier pigeon"}', encoding="utf-8")
    assert Settings.load(store).screen_reader_output == default_output().id


def test_unsupported_language_is_ignored(tmp_path: Path) -> None:
    store = tmp_path / "settings.json"
    store.write_text('{"language": "xx", "unknown": 1}', encoding="utf-8")
    assert Settings.load(store).language == "fr"


def test_invalid_json_raises(tmp_path: Path) -> None:
    store = tmp_path / "settings.json"
    store.write_text("{", encoding="utf-8")
    with pytest.raises(SettingsError):
        Settings.load(store)
