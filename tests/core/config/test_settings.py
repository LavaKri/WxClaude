import json
from pathlib import Path

import pytest

from wxclaude.core.config.agents import DEFAULT_AGENT, Agent
from wxclaude.core.config.settings import Settings
from wxclaude.core.config.shortcuts import INTERRUPT_COMMAND, NEW_CONVERSATION_COMMAND
from wxclaude.core.conversation.conversations import new_conversation_id
from wxclaude.core.errors import SettingsError
from wxclaude.core.speech.announcements import END_OF_ANSWER, PROGRESS, Destination
from wxclaude.core.speech.screen_reader import default_output

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
    settings.default_agent = Agent(model="opus", effort="high", permission_mode="plan")
    settings.alternative_agent = Agent(model="haiku", permission_mode="plan")
    settings.recent_workspaces = ["C:\\work\\one"]
    settings.save()
    loaded = Settings.load(store)
    assert loaded.language == "en"
    assert loaded.default_agent == Agent(model="opus", effort="high", permission_mode="plan")
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


def test_the_last_workspace_and_conversation_are_reopened_by_default(tmp_path: Path) -> None:
    settings = Settings.load(tmp_path / "settings.json")
    assert settings.reopen_last is True
    assert settings.conversation_counter == 1


def test_last_session_round_trip_and_invalid_values(tmp_path: Path) -> None:
    store = tmp_path / "settings.json"
    settings = Settings.load(store)
    settings.reopen_last = False
    settings.last_workspace = str(tmp_path / "Work")
    settings.conversation_counter = 7
    settings.save()
    loaded = Settings.load(store)
    assert (loaded.reopen_last, loaded.last_workspace) == (False, str(tmp_path / "Work"))
    assert loaded.conversation_counter == 7
    assert loaded.workspaces_dir == tmp_path / "workspaces"
    store.write_text(
        json.dumps({"reopen_last": "yes", "conversation_counter": 0}), encoding="utf-8"
    )
    invalid = Settings.load(store)
    assert (invalid.reopen_last, invalid.conversation_counter) == (True, 1)


def test_the_hide_system_messages_option_defaults_to_true_and_round_trips(
    tmp_path: Path,
) -> None:
    store = tmp_path / "settings.json"
    settings = Settings.load(store)
    assert settings.hide_system_messages is True
    settings.hide_system_messages = False
    settings.save()
    assert Settings.load(store).hide_system_messages is False
    store.write_text('{"hide_system_messages": "no"}', encoding="utf-8")
    assert Settings.load(store).hide_system_messages is True


def test_the_destination_of_a_category_defaults_and_only_a_change_is_stored(
    tmp_path: Path,
) -> None:
    store = tmp_path / "settings.json"
    settings = Settings.load(store)
    assert settings.destination_for(END_OF_ANSWER) is Destination.SOUND_1
    settings.set_destination(END_OF_ANSWER, Destination.MESSAGE)
    settings.set_destination(PROGRESS, Destination.MESSAGE)  # the default: not stored
    assert settings.announcements == {"end_of_answer": "message"}
    settings.save()
    loaded = Settings.load(store)
    assert loaded.destination_for(END_OF_ANSWER) is Destination.MESSAGE
    loaded.set_destination(END_OF_ANSWER, Destination.SOUND_1)
    assert loaded.announcements == {}


def test_an_unknown_or_unaccepted_destination_in_the_file_is_ignored(tmp_path: Path) -> None:
    store = tmp_path / "settings.json"
    store.write_text(
        json.dumps(
            {"announcements": {"progress": "sound_1", "end_of_answer": "x", "nothing": "none"}}
        ),
        encoding="utf-8",
    )
    settings = Settings.load(store)
    assert settings.announcements == {}
    assert settings.destination_for(PROGRESS) is Destination.MESSAGE
    store.write_text('{"announcements": 3}', encoding="utf-8")
    assert Settings.load(store).announcements == {}


def test_the_claude_path_options_default_to_the_automatic_search_and_round_trip(
    tmp_path: Path,
) -> None:
    store = tmp_path / "settings.json"
    settings = Settings.load(store)
    assert settings.claude_auto_search
    assert settings.claude_path == ""
    settings.claude_auto_search = False
    settings.claude_path = "C:/tools/claude.exe"
    settings.save()
    again = Settings.load(store)
    assert not again.claude_auto_search
    assert again.claude_path == "C:/tools/claude.exe"
    store.write_text('{"claude_auto_search": "no", "claude_path": 3}', encoding="utf-8")
    invalid = Settings.load(store)
    assert invalid.claude_auto_search
    assert invalid.claude_path == ""


def test_the_permission_channel_defaults_to_stdio_with_ten_minutes_and_round_trips(
    tmp_path: Path,
) -> None:
    store = tmp_path / "settings.json"
    settings = Settings.load(store)
    assert (settings.permission_channel, settings.hook_timeout_minutes) == ("stdio", 10)
    settings.permission_channel = "hook"
    settings.hook_timeout_minutes = 3
    settings.save()
    again = Settings.load(store)
    assert (again.permission_channel, again.hook_timeout_minutes) == ("hook", 3)


@pytest.mark.parametrize(
    ("channel", "minutes"), [("pigeon", 0), (3, 11), ("", -1), (None, True), ("hook", 2.5)]
)
def test_an_invalid_permission_channel_or_waiting_time_is_ignored(
    tmp_path: Path, channel: object, minutes: object
) -> None:
    store = tmp_path / "settings.json"
    store.write_text(
        json.dumps({"permission_channel": channel, "hook_timeout_minutes": minutes}),
        encoding="utf-8",
    )
    loaded = Settings.load(store)
    assert loaded.hook_timeout_minutes == 10
    assert loaded.permission_channel == ("hook" if channel == "hook" else "stdio")


def test_the_default_agent_is_always_complete(tmp_path: Path) -> None:
    store = tmp_path / "settings.json"
    store.write_text('{"default_agent": {"model": "opus"}}', encoding="utf-8")
    assert Settings.load(store).default_agent == Agent(
        model="opus", effort="medium", permission_mode="manual"
    )
    store.write_text("{}", encoding="utf-8")
    assert Settings.load(store).default_agent == DEFAULT_AGENT


def test_the_older_conversation_keys_are_ignored(tmp_path: Path) -> None:
    store = tmp_path / "settings.json"
    old_data = {
        "last_workspace": str(tmp_path),
        "last_conversation_id": new_conversation_id(),
        "workspace_conversations": {"x": new_conversation_id()},
    }
    store.write_text(json.dumps(old_data), encoding="utf-8")
    loaded = Settings.load(store)
    assert loaded.last_workspace == str(tmp_path)
    loaded.save()
    saved = json.loads(store.read_text(encoding="utf-8"))
    assert "last_conversation_id" not in saved
    assert "workspace_conversations" not in saved


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


def test_a_damaged_file_gives_the_defaults_and_a_warning(tmp_path: Path) -> None:
    store = tmp_path / "settings.json"
    store.write_text("{", encoding="utf-8")
    settings = Settings.load(store)
    assert settings.language == "fr"
    assert "settings.json" in settings.load_warning
    assert (tmp_path / "settings.json.corrupt").exists()


def test_a_save_that_fails_raises_settings_error(tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("a file, not a folder", encoding="utf-8")
    settings = Settings.load(blocker / "settings.json")
    with pytest.raises(SettingsError):
        settings.save()
