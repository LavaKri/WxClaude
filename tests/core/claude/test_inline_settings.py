"""The one --settings argument, merged from the parts of a launch."""

import json
from typing import cast

import pytest

from wxclaude.core.claude.inline_settings import merge_settings, settings_arguments

pytestmark = pytest.mark.unit


def test_nothing_to_give_is_no_argument() -> None:
    assert settings_arguments() == []
    assert settings_arguments({}, {}) == []


def test_one_part_is_given_as_it_is() -> None:
    part: dict[str, object] = {"env": {"A": "1"}}
    assert settings_arguments(part) == ["--settings", json.dumps(part)]


def test_objects_are_merged_key_by_key() -> None:
    merged = merge_settings({"env": {"A": "1"}}, {"env": {"B": "2"}, "model": "haiku"})
    assert merged == {"env": {"A": "1", "B": "2"}, "model": "haiku"}


def test_lists_are_joined_and_an_entry_stays_once() -> None:
    first: dict[str, object] = {
        "hooks": {"PermissionRequest": [{"hooks": [{"type": "http", "url": "u"}]}]},
        "permissions": {"deny": ["Read(.env)"]},
    }
    second: dict[str, object] = {
        "permissions": {"deny": ["Read(.env)", "Bash(rm *)"], "ask": ["Edit"]},
    }
    merged = merge_settings(first, second)
    assert merged["hooks"] == first["hooks"]
    assert merged["permissions"] == {"deny": ["Read(.env)", "Bash(rm *)"], "ask": ["Edit"]}


def test_a_later_value_replaces_an_earlier_one() -> None:
    assert merge_settings({"model": "a", "env": {"X": "1"}}, {"model": "b", "env": {"X": "2"}}) == {
        "model": "b",
        "env": {"X": "2"},
    }


def test_a_value_of_another_kind_replaces_the_earlier_one() -> None:
    assert merge_settings({"a": {"x": 1}}, {"a": [1]}) == {"a": [1]}


def test_the_parts_are_not_changed() -> None:
    first: dict[str, object] = {"permissions": {"deny": ["A"]}}
    second: dict[str, object] = {"permissions": {"deny": ["B"]}}
    merged = merge_settings(first, second)
    cast(dict[str, list[str]], merged["permissions"])["deny"].append("C")
    assert first == {"permissions": {"deny": ["A"]}}
    assert second == {"permissions": {"deny": ["B"]}}
