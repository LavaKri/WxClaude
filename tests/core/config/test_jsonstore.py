from pathlib import Path

import pytest

from wxclaude.core.config.jsonstore import read_json, write_json
from wxclaude.core.errors import JsonStoreError

pytestmark = pytest.mark.unit


def test_a_missing_file_is_not_an_error(tmp_path: Path) -> None:
    result = read_json(tmp_path / "a.json")
    assert (result.data, result.warning) == (None, "")


def test_write_then_read_and_no_temporary_file_is_left(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "a.json"
    write_json(path, {"x": 1, "text": "é"})
    assert read_json(path).data == {"x": 1, "text": "é"}
    assert [file.name for file in path.parent.iterdir()] == ["a.json"]


def test_the_previous_version_is_kept_as_a_backup(tmp_path: Path) -> None:
    path = tmp_path / "a.json"
    write_json(path, {"v": 1})
    write_json(path, {"v": 2})
    assert read_json(path).data == {"v": 2}
    assert read_json(tmp_path / "a.json.bak").data == {"v": 1}


def test_a_damaged_file_is_set_aside_and_the_backup_is_used(tmp_path: Path) -> None:
    path = tmp_path / "a.json"
    write_json(path, {"v": 1})
    write_json(path, {"v": 2})
    path.write_text('{"v": ', encoding="utf-8")
    result = read_json(path)
    assert result.data == {"v": 1}
    assert "backup" in result.warning
    assert (tmp_path / "a.json.corrupt").read_text(encoding="utf-8") == '{"v": '
    assert not path.exists()


def test_a_damaged_file_without_backup_gives_defaults(tmp_path: Path) -> None:
    path = tmp_path / "a.json"
    path.write_text("[1, 2]", encoding="utf-8")  # valid JSON but not an object
    result = read_json(path)
    assert result.data is None
    assert "default" in result.warning


def test_a_damaged_file_never_replaces_the_good_backup(tmp_path: Path) -> None:
    path = tmp_path / "a.json"
    write_json(path, {"v": 1})
    write_json(path, {"v": 2})
    path.write_text("{", encoding="utf-8")
    write_json(path, {"v": 3})
    assert read_json(tmp_path / "a.json.bak").data == {"v": 1}
    assert read_json(path).data == {"v": 3}


def test_a_write_that_cannot_be_done_raises(tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    with pytest.raises(JsonStoreError):
        write_json(blocker / "a.json", {})
