"""The real files of Claude Code behind ``ClaudeFiles``: each method reaches the right folder."""

import json
from pathlib import Path

import pytest

from wxclaude.core.claude_files import ClaudeFiles, DiskClaudeFiles
from wxclaude.core.errors import SessionReadError

pytestmark = pytest.mark.unit

SESSION = "d278c1fc-1d73-4c16-a899-5bdb1831fe5c"


@pytest.fixture
def config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    folder = tmp_path / "claude-config"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(folder))
    return folder


def test_the_disk_files_follow_the_contract() -> None:
    files: ClaudeFiles = DiskClaudeFiles()  # mypy checks the Protocol here
    assert files is not None


def test_nothing_is_found_in_an_empty_configuration(config: Path, tmp_path: Path) -> None:
    files = DiskClaudeFiles()
    assert files.list_sessions(tmp_path) == []
    assert files.find_session(SESSION) is None
    assert files.load_tasks(SESSION).tasks == []
    assert files.load_plans(SESSION) == []
    assert files.list_projects() == []
    with pytest.raises(SessionReadError):
        files.read_session(tmp_path / "missing.jsonl")


def test_a_session_and_its_tasks_are_read_from_the_configuration(
    config: Path, tmp_path: Path
) -> None:
    project = config / "projects" / "folder"
    project.mkdir(parents=True)
    entry = {
        "type": "user",
        "cwd": str(tmp_path),
        "uuid": "u",
        "timestamp": "2026-10-23T10:00:00+00:00",
        "message": {"role": "user", "content": "Hello"},
    }
    (project / f"{SESSION}.jsonl").write_text(json.dumps(entry), encoding="utf-8")
    tasks = config / "tasks" / SESSION
    tasks.mkdir(parents=True)
    task = {"id": "1", "subject": "Alpha", "status": "pending"}
    (tasks / "1.json").write_text(json.dumps(task), encoding="utf-8")
    files = DiskClaudeFiles()
    path = files.find_session(SESSION)
    assert path is not None
    assert [message.text for message in files.read_session(path).messages] == ["Hello"]
    assert [session.id for session in files.list_sessions(tmp_path)] == [SESSION]
    assert [task.subject for task in files.load_tasks(SESSION).tasks] == ["Alpha"]


def test_always_allow_writes_the_personal_settings_file(config: Path, tmp_path: Path) -> None:
    DiskClaudeFiles().allow_always(tmp_path, "Bash(touch x)")
    local = json.loads((tmp_path / ".claude" / "settings.local.json").read_text(encoding="utf-8"))
    assert local["permissions"]["allow"] == ["Bash(touch x)"]
