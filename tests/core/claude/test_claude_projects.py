import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from wxclaude.core.claude.claude_projects import (
    SessionInfo,
    choose_conversation,
    find_session_file,
    list_projects,
    list_sessions,
    session_paths,
)
from wxclaude.core.conversation.conversations import new_conversation_id

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


def _conversation_file(
    folder: Path, session_id: str, cwd: Path, *titles: dict[str, object]
) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    file = folder / f"{session_id}.jsonl"
    lines = [json.dumps({"type": "user", "cwd": str(cwd)})]
    lines += [json.dumps(title) for title in titles]
    file.write_text("\n".join(lines), encoding="utf-8")
    return file


def test_sessions_of_a_workspace_with_their_titles(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    projects = tmp_path / "projects"
    first, second = new_conversation_id(), new_conversation_id()
    old = _conversation_file(
        projects / "C--work",
        first,
        work,
        {"type": "ai-title", "aiTitle": "Generated"},
        {"type": "custom-title", "customTitle": "Mine"},
    )
    os.utime(old, (old.stat().st_mtime - 100,) * 2)
    _conversation_file(projects / "C--work", second, work, {"type": "ai-title", "aiTitle": "Gen"})
    _conversation_file(projects / "C--work", "not-an-id", work)
    _conversation_file(projects / "C--other", new_conversation_id(), tmp_path / "other")
    sessions = list_sessions(work, projects)
    assert [(s.id, s.title) for s in sessions] == [(second, "Gen"), (first, "Mine")]


def test_sessions_of_an_unknown_workspace_or_folder(tmp_path: Path) -> None:
    assert list_sessions(tmp_path, tmp_path / "nothing") == []


def _message_line(when: datetime) -> dict[str, object]:
    return {"type": "assistant", "timestamp": when.isoformat(), "message": {"content": []}}


def test_sessions_are_sorted_by_their_last_message_not_by_file_date(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    projects = tmp_path / "projects"
    now = datetime.now(UTC)
    renamed_later, talked_later = new_conversation_id(), new_conversation_id()
    first = _conversation_file(
        projects / "C--work",
        renamed_later,
        work,
        _message_line(now - timedelta(hours=2)),
        {"type": "custom-title", "customTitle": "Renamed"},  # the file is written last
    )
    second = _conversation_file(
        projects / "C--work", talked_later, work, _message_line(now - timedelta(hours=1))
    )
    os.utime(second, (second.stat().st_mtime - 1000,) * 2)
    assert first.stat().st_mtime > second.stat().st_mtime
    sessions = list_sessions(work, projects)
    assert [s.id for s in sessions] == [talked_later, renamed_later]
    assert sessions[1].last_used == pytest.approx((now - timedelta(hours=2)).timestamp())


def test_the_remembered_conversation_is_chosen_else_the_most_recent_else_none(
    tmp_path: Path,
) -> None:
    def info(name: str, used: float) -> SessionInfo:
        return SessionInfo(name, tmp_path / name, "", used)

    recent, old = info("recent", 2.0), info("old", 1.0)
    assert choose_conversation([recent, old], "old") is old
    assert choose_conversation([recent, old], "gone") is recent
    assert choose_conversation([recent, old], "") is recent
    assert choose_conversation([], "old") is None


def test_a_session_file_is_found_by_its_identifier(tmp_path: Path) -> None:
    projects = tmp_path / "projects"
    identifier = new_conversation_id()
    file = _conversation_file(projects / "C--work", identifier, tmp_path)
    assert find_session_file(identifier, projects) == file
    assert find_session_file(new_conversation_id(), projects) is None
    assert find_session_file(identifier, tmp_path / "nothing") is None


def test_the_files_of_a_session_are_its_transcript_its_folder_its_history_and_its_tasks(
    tmp_path: Path,
) -> None:
    identifier = new_conversation_id()
    transcript = _conversation_file(tmp_path / "projects" / "C--work", identifier, tmp_path)
    beside = transcript.with_suffix("")
    (beside / "subagents").mkdir(parents=True)
    history = tmp_path / "file-history" / identifier
    history.mkdir(parents=True)
    tasks = tmp_path / "tasks" / identifier
    assert session_paths(identifier, tmp_path) == [transcript, beside, history]
    tasks.mkdir(parents=True)
    assert session_paths(identifier, tmp_path)[-1] == tasks
    assert session_paths(new_conversation_id(), tmp_path) == []  # no history yet


@pytest.mark.parametrize("identifier", ["", "..", "not-an-id"])
def test_what_is_not_a_session_identifier_names_no_file(tmp_path: Path, identifier: str) -> None:
    (tmp_path / "file-history").mkdir()
    (tmp_path / "tasks").mkdir()
    assert session_paths(identifier, tmp_path) == []
