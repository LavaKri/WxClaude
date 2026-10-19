"""User settings, stored as JSON in the user configuration folder."""

import json
from dataclasses import dataclass, field
from pathlib import Path

from platformdirs import user_config_dir

from wxclaude.core.agents import Agent
from wxclaude.core.errors import SettingsError

SETTINGS_FILE_NAME = "settings.json"
SUPPORTED_LANGUAGES = ("fr", "en")


def default_settings_path() -> Path:
    """Location of the settings file for the current user."""
    return Path(user_config_dir("WxClaude")) / SETTINGS_FILE_NAME


@dataclass(slots=True)
class Settings:
    """Application settings. Unknown keys in the file are ignored."""

    language: str = "fr"
    default_agent: Agent = field(default_factory=Agent)
    alternative_agent: Agent = field(default_factory=lambda: Agent(effort="low"))
    recent_workspaces: list[str] = field(default_factory=list)
    store: Path | None = None

    @classmethod
    def load(cls, store: Path | None) -> Settings:
        """Read settings from ``store``; defaults if absent. ``store=None`` stays in memory."""
        settings = cls(store=store)
        if store is None or not store.exists():
            return settings
        try:
            data = json.loads(store.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise SettingsError(f"Cannot read {store}: {error}") from error
        if not isinstance(data, dict):
            raise SettingsError(f"Invalid settings file: {store}")
        language = data.get("language")
        if language in SUPPORTED_LANGUAGES:
            settings.language = language
        if "default_agent" in data:
            settings.default_agent = Agent.from_dict(data["default_agent"])
        if "alternative_agent" in data:
            settings.alternative_agent = Agent.from_dict(data["alternative_agent"])
        recent = data.get("recent_workspaces")
        if isinstance(recent, list):
            settings.recent_workspaces = [item for item in recent if isinstance(item, str)]
        return settings

    def save(self) -> None:
        """Write the settings to their store, if any."""
        if self.store is None:
            return
        data = {
            "language": self.language,
            "default_agent": self.default_agent.to_dict(),
            "alternative_agent": self.alternative_agent.to_dict(),
            "recent_workspaces": self.recent_workspaces,
        }
        try:
            self.store.parent.mkdir(parents=True, exist_ok=True)
            self.store.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError as error:
            raise SettingsError(f"Cannot write {self.store}: {error}") from error
