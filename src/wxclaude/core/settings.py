"""User settings, stored as JSON in the user configuration folder."""

from dataclasses import dataclass, field
from pathlib import Path

from platformdirs import user_config_dir

from wxclaude.core.agents import DEFAULT_AGENT, Agent
from wxclaude.core.errors import JsonStoreError, SettingsError
from wxclaude.core.jsonstore import read_json, write_json
from wxclaude.core.screen_reader import default_output, output_named
from wxclaude.core.shortcuts import (
    CONFIGURABLE_COMMANDS,
    ConfigurableCommand,
    check_shortcut,
    normalize_shortcut,
)

SETTINGS_FILE_NAME = "settings.json"
_FLAG_KEYS = (
    "reopen_last",
    "hide_system_messages",
    "announce_progress",
    "local_tools_only",
    "claude_auto_search",
)
_TEXT_KEYS = ("claude_path", "last_workspace")
SUPPORTED_LANGUAGES = ("fr", "en")


def workspace_key(folder: Path) -> str:
    """How a workspace is named in the settings (Windows paths ignore the case)."""
    return str(folder).lower()


def default_settings_path() -> Path:
    """Location of the settings file for the current user."""
    return Path(user_config_dir("WxClaude")) / SETTINGS_FILE_NAME


@dataclass(slots=True)
class Settings:
    """Application settings. Unknown keys in the file are ignored."""

    language: str = "fr"
    default_agent: Agent = DEFAULT_AGENT  # complete: model, effort and permission mode
    alternative_agent: Agent = field(default_factory=lambda: Agent(effort="low"))
    recent_workspaces: list[str] = field(default_factory=list)
    shortcuts: dict[str, str] = field(default_factory=dict)  # only the changed ones
    screen_reader_output: str = field(default_factory=lambda: default_output().id)
    reopen_last: bool = True  # open the last workspace and conversation at startup
    hide_system_messages: bool = True  # do not show the noise the CLI writes in a session
    announce_progress: bool = True  # say what Claude is doing while it answers
    local_tools_only: bool = False  # never modify the versioned settings of a project
    claude_auto_search: bool = True  # look for claude in the PATH instead of using claude_path
    claude_path: str = ""  # the claude executable chosen by hand (used without the auto search)
    last_workspace: str = ""
    conversation_counter: int = 1  # the number of the next "Conversation x" proposed
    store: Path | None = None
    load_warning: str = ""  # what went wrong while reading the file, for the user

    @property
    def workspaces_dir(self) -> Path | None:
        """The folder of the per-workspace files (None: settings kept in memory only)."""
        return None if self.store is None else self.store.parent / "workspaces"

    def shortcut_for(self, command: ConfigurableCommand) -> str:
        """The shortcut of ``command`` (empty: none)."""
        return self.shortcuts.get(command.id, command.default)

    def set_shortcut(self, command: ConfigurableCommand, shortcut: str) -> None:
        """Give ``shortcut`` to ``command``; only a difference from the default is stored."""
        if shortcut == command.default:
            self.shortcuts.pop(command.id, None)
        else:
            self.shortcuts[command.id] = shortcut

    def all_shortcuts(self) -> dict[str, str]:
        """The shortcut of every configurable command, by command id."""
        return {command.id: self.shortcut_for(command) for command in CONFIGURABLE_COMMANDS}

    @classmethod
    def load(cls, store: Path | None) -> Settings:
        """Read settings from ``store``; defaults if absent. ``store=None`` stays in memory."""
        settings = cls(store=store)
        if store is None:
            return settings
        result = read_json(store)
        settings.load_warning = result.warning
        if result.data is not None:
            settings._apply_values(result.data)
            settings._apply_agents(result.data)
            settings._apply_shortcuts(result.data)
        return settings

    def _apply_values(self, data: dict[str, object]) -> None:
        """The plain values of the file; a value of the wrong kind is ignored."""
        language = data.get("language")
        if language in SUPPORTED_LANGUAGES:
            self.language = str(language)
        recent = data.get("recent_workspaces")
        if isinstance(recent, list):
            self.recent_workspaces = [item for item in recent if isinstance(item, str)]
        for key in _FLAG_KEYS:
            flag = data.get(key)
            if isinstance(flag, bool):
                setattr(self, key, flag)
        for key in _TEXT_KEYS:
            text = data.get(key)
            if isinstance(text, str):
                setattr(self, key, text)
        counter = data.get("conversation_counter")
        if isinstance(counter, int) and not isinstance(counter, bool) and counter >= 1:
            self.conversation_counter = counter
        output = data.get("screen_reader_output")
        if isinstance(output, str) and output_named(output) is not None:
            self.screen_reader_output = output

    def _apply_agents(self, data: dict[str, object]) -> None:
        if "default_agent" in data:
            self.default_agent = Agent.from_dict(data["default_agent"]).over(DEFAULT_AGENT)
        if "alternative_agent" in data:
            self.alternative_agent = Agent.from_dict(data["alternative_agent"])

    def _apply_shortcuts(self, data: dict[str, object]) -> None:
        """The shortcuts that differ from the default; invalid or conflicting ones are ignored."""
        saved = data.get("shortcuts")
        if not isinstance(saved, dict):
            return
        for command in CONFIGURABLE_COMMANDS:
            value = saved.get(command.id)
            normalized = normalize_shortcut(value) if isinstance(value, str) else None
            if normalized is None:
                continue
            if check_shortcut(command, normalized, self.all_shortcuts()).problem is None:
                self.set_shortcut(command, normalized)

    def save(self) -> None:
        """Write the settings to their store, if any."""
        if self.store is None:
            return
        data: dict[str, object] = {
            "language": self.language,
            "default_agent": self.default_agent.to_dict(),
            "alternative_agent": self.alternative_agent.to_dict(),
            "recent_workspaces": self.recent_workspaces,
            "shortcuts": self.shortcuts,
            "screen_reader_output": self.screen_reader_output,
            "reopen_last": self.reopen_last,
            "hide_system_messages": self.hide_system_messages,
            "announce_progress": self.announce_progress,
            "local_tools_only": self.local_tools_only,
            "claude_auto_search": self.claude_auto_search,
            "claude_path": self.claude_path,
            "last_workspace": self.last_workspace,
            "conversation_counter": self.conversation_counter,
        }
        try:
            write_json(self.store, data)
        except JsonStoreError as error:
            raise SettingsError(str(error)) from error
