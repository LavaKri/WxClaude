import json
import os
from pathlib import Path

import pytest

from wxclaude.core.claude_projects import list_projects

pytestmark = pytest.mark.unit


def _session(projects: Path, name: str, cwd: Path | None, age: int = 0) -> Path:
    folder = projects / name
    folder.mkdir(parents=True)
    file = folder / "session.jsonl"
    lines = [json.dumps({"type": "queue-operation"})]
    if cwd is not None:
        lines.append(json.dumps({"type": "user", "cwd": str(cwd)}))
    file.write_text("\n".join(lines), encoding="utf-8")
    stamp = file.stat().st_mtime - age
    os.utime(file, (stamp, stamp))
    return file


def test_the_working_folder_is_read_from_the_session_file(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    _session(tmp_path / "projects", "C--work", work)
    assert [project.folder for project in list_projects(tmp_path / "projects")] == [work]


def test_projects_are_sorted_by_last_use(tmp_path: Path) -> None:
    old, recent = tmp_path / "old", tmp_path / "recent"
    old.mkdir()
    recent.mkdir()
    _session(tmp_path / "projects", "old", old, age=1000)
    _session(tmp_path / "projects", "recent", recent)
    folders = [project.folder for project in list_projects(tmp_path / "projects")]
    assert folders == [recent, old]


def test_missing_folders_and_sessions_without_a_folder_are_ignored(tmp_path: Path) -> None:
    _session(tmp_path / "projects", "gone", tmp_path / "does-not-exist")
    _session(tmp_path / "projects", "unknown", None)
    (tmp_path / "projects" / "empty").mkdir()
    assert list_projects(tmp_path / "projects") == []


def test_a_missing_projects_folder_gives_an_empty_list(tmp_path: Path) -> None:
    assert list_projects(tmp_path / "nothing") == []
