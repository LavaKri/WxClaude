import os
from pathlib import Path

import pytest

from wxclaude.core.workspaces import MAX_RECENT, add_recent, describe, remove_missing

pytestmark = pytest.mark.unit


def test_add_recent_moves_existing_folder_to_front(tmp_path: Path) -> None:
    first, second = tmp_path / "a", tmp_path / "b"
    recent = add_recent(add_recent([], first), second)
    assert add_recent(recent, first) == [str(first), str(second)]


def test_add_recent_is_limited() -> None:
    recent: list[str] = []
    for index in range(MAX_RECENT + 5):
        recent = add_recent(recent, Path(f"C:/folder{index}"))
    assert len(recent) == MAX_RECENT


def test_remove_missing_drops_deleted_folders(tmp_path: Path) -> None:
    kept = tmp_path / "kept"
    kept.mkdir()
    assert remove_missing([str(kept), str(tmp_path / "gone")]) == [str(kept)]


def test_describe_gives_name_and_parent() -> None:
    name, parent = describe(str(Path("C:/Users/Example/Dev/WxClaude")))
    assert name == "WxClaude"
    assert parent == str(Path("C:/Users/Example/Dev")) + os.sep
