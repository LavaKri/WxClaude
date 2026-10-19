from pathlib import Path

import pytest

from wxclaude.core.errors import SettingsError
from wxclaude.core.settings import Settings

pytestmark = pytest.mark.unit


def test_defaults_when_file_is_missing(tmp_path: Path) -> None:
    assert Settings.load(tmp_path / "settings.json").language == "fr"


def test_save_then_load_round_trip(tmp_path: Path) -> None:
    store = tmp_path / "settings.json"
    settings = Settings.load(store)
    settings.language = "en"
    settings.save()
    assert Settings.load(store).language == "en"


def test_unsupported_language_is_ignored(tmp_path: Path) -> None:
    store = tmp_path / "settings.json"
    store.write_text('{"language": "xx", "unknown": 1}', encoding="utf-8")
    assert Settings.load(store).language == "fr"


def test_invalid_json_raises(tmp_path: Path) -> None:
    store = tmp_path / "settings.json"
    store.write_text("{", encoding="utf-8")
    with pytest.raises(SettingsError):
        Settings.load(store)
