"""User settings, stored as JSON in the user configuration folder."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from platformdirs import user_config_dir

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
        return settings

    def save(self) -> None:
        """Write the settings to their store, if any."""
        if self.store is None:
            return
        data = asdict(self)
        del data["store"]
        try:
            self.store.parent.mkdir(parents=True, exist_ok=True)
            self.store.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError as error:
            raise SettingsError(f"Cannot write {self.store}: {error}") from error
