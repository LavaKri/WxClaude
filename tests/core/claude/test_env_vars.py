"""The environment variables of Claude Code: the described list and the env key of a file."""

import json
from pathlib import Path

import pytest

from wxclaude.core.claude.claude_settings import SettingsFile, Source
from wxclaude.core.claude.env_vars import (
    FLAG,
    VALUE,
    env_of,
    env_rows,
    known_env_vars,
    parse_env_vars,
    remove_env,
    set_env,
)
from wxclaude.core.errors import ClaudeSettingsError

pytestmark = pytest.mark.unit

TEXT = """# a comment

FOO_FLAG | flag | any | Does a thing.
FOO_VALUE | value | user | Takes a number. | with a bar
not a line
BAD_KIND | maybe | any | x
 | flag | any | no name
ANTHROPIC_BASE_URL | value | any | chosen by the provider
ANTHROPIC_DEFAULT_HAIKU_MODEL | value | any | chosen by the provider
"""


def file_with(
    tmp_path: Path, data: object | None = None, source: Source = Source.LOCAL
) -> SettingsFile:
    path = tmp_path / "settings.json"
    if data is not None:
        path.write_text(json.dumps(data), encoding="utf-8")
    return SettingsFile.load(source, path)


def test_the_format_of_the_list() -> None:
    infos = parse_env_vars(TEXT)
    assert [(i.name, i.kind, i.project_ignored) for i in infos] == [
        ("FOO_FLAG", FLAG, False),
        ("FOO_VALUE", VALUE, True),
    ]
    assert infos[1].text == "Takes a number. | with a bar"  # the text may hold a bar


def test_the_variables_of_the_provider_are_never_offered() -> None:
    assert (
        parse_env_vars(
            "ANTHROPIC_AUTH_TOKEN | value | any | x\nANTHROPIC_API_KEY | value | any | x"
        )
        == []
    )


def test_the_list_that_ships_with_the_application_is_well_formed() -> None:
    infos = known_env_vars()
    names = [info.name for info in infos]
    assert len(infos) > 30
    assert len(set(names)) == len(names)
    assert all(info.text.endswith(".") or info.text.endswith(")") for info in infos)
    assert "CLAUDE_CODE_DISABLE_WEB_FETCH" in names
    assert not any(name.startswith("ANTHROPIC_") for name in names)


def test_rows_hold_the_described_variables_and_those_the_file_adds(tmp_path: Path) -> None:
    file = file_with(tmp_path, {"env": {"FOO_FLAG": "1", "OTHER": "x", "ANTHROPIC_BASE_URL": "u"}})
    rows = env_rows(file, parse_env_vars(TEXT))
    assert [(r.name, r.value) for r in rows] == [
        ("FOO_FLAG", "1"),
        ("FOO_VALUE", None),
        ("OTHER", "x"),  # not described: kept, last
    ]
    assert rows[0].is_flag
    assert not rows[2].is_flag
    assert rows[2].info is None
    assert "not described" in rows[2].explanation
    assert rows[0].explanation == "Does a thing."


def test_sensitive_names_are_marked(tmp_path: Path) -> None:
    file = file_with(tmp_path, {"env": {"MY_TOKEN": "a", "HTTPS_PROXY": "b", "MODEL": "c"}})
    marks = {r.name: r.sensitive for r in env_rows(file, [])}
    assert marks == {"HTTPS_PROXY": True, "MODEL": False, "MY_TOKEN": True}


def test_only_text_values_are_read(tmp_path: Path) -> None:
    file = file_with(tmp_path, {"env": {"A": "1", "B": 2, "C": None}})
    assert env_of(file) == {"A": "1"}
    assert env_of(file_with(tmp_path, {"env": "nope"})) == {}
    assert env_of(file_with(tmp_path)) == {}


def test_setting_and_removing_keep_the_rest_of_the_file(tmp_path: Path) -> None:
    file = file_with(tmp_path, {"permissions": {"allow": ["Bash"]}, "env": {"A": "1"}})
    set_env(file, "B", "2")
    assert file.changed
    assert file.data == {"permissions": {"allow": ["Bash"]}, "env": {"A": "1", "B": "2"}}
    remove_env(file, "A")
    assert file.data["env"] == {"B": "2"}
    assert file.data["permissions"] == {"allow": ["Bash"]}


def test_a_file_without_env_gets_one(tmp_path: Path) -> None:
    file = file_with(tmp_path)
    set_env(file, "A", "1")
    assert file.data == {"env": {"A": "1"}}


def test_nothing_changes_when_nothing_changes(tmp_path: Path) -> None:
    file = file_with(tmp_path, {"env": {"A": "1"}})
    set_env(file, "A", "1")
    remove_env(file, "ABSENT")
    assert not file.changed


def test_the_variables_of_the_provider_cannot_be_set(tmp_path: Path) -> None:
    with pytest.raises(ClaudeSettingsError, match="provider"):
        set_env(file_with(tmp_path), "ANTHROPIC_BASE_URL", "https://x")


def test_a_damaged_file_and_the_general_file_are_never_written(tmp_path: Path) -> None:
    damaged = tmp_path / "bad.json"
    damaged.write_text("{not json", encoding="utf-8")
    with pytest.raises(ClaudeSettingsError):
        set_env(SettingsFile.load(Source.LOCAL, damaged), "A", "1")
    with pytest.raises(ClaudeSettingsError):
        remove_env(file_with(tmp_path, {"env": {"A": "1"}}, Source.GENERAL), "A")
