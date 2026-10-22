import json
from pathlib import Path

import pytest

from wxclaude.core.claude.tasks import Step, Task, TaskList, load_tasks, started_task_id, step_of
from wxclaude.core.errors import TaskReadError

pytestmark = pytest.mark.unit

SESSION = "d278c1fc-1d73-4c16-a899-5bdb1831fe5c"


def _write(config: Path, name: str, content: object) -> None:
    folder = config / "tasks" / SESSION
    folder.mkdir(parents=True, exist_ok=True)
    text = content if isinstance(content, str) else json.dumps(content)
    (folder / name).write_text(text, encoding="utf-8")


def test_only_a_task_update_to_in_progress_starts_a_step() -> None:
    assert started_task_id("TaskUpdate", {"taskId": "2", "status": "in_progress"}) == "2"
    assert started_task_id("TaskUpdate", {"taskId": 3, "status": "in_progress"}) == "3"
    assert started_task_id("TaskUpdate", {"taskId": "2", "status": "completed"}) is None
    assert started_task_id("TaskUpdate", {"status": "in_progress"}) is None
    assert started_task_id("TaskCreate", {"subject": "A", "status": "in_progress"}) is None


def test_a_step_is_the_place_of_the_task_in_the_list() -> None:
    tasks = TaskList([Task("1", "Alpha", "", "completed"), Task("2", "Beta", "", "in_progress")])
    assert step_of("2", tasks) == Step(2, 2, "Beta")
    assert step_of("7", tasks) is None


def test_no_folder_means_no_task(tmp_path: Path) -> None:
    result = load_tasks(SESSION, tmp_path)
    assert result.tasks == []
    assert result.unreadable == []


def test_tasks_are_read_and_sorted_by_number(tmp_path: Path) -> None:
    _write(tmp_path, "10.json", {"id": "10", "subject": "Last", "status": "pending"})
    _write(
        tmp_path,
        "2.json",
        {
            "id": "2",
            "subject": "Second",
            "description": "More",
            "status": "in_progress",
            "blockedBy": ["1"],
            "activeForm": "ignored",
        },
    )
    _write(tmp_path, "1.json", {"id": "1", "subject": "First", "status": "completed"})
    _write(tmp_path, ".lock", "")
    result = load_tasks(SESSION, tmp_path)
    assert [task.id for task in result.tasks] == ["1", "2", "10"]
    assert result.tasks[1] == Task("2", "Second", "More", "in_progress", ("1",))


def test_a_file_that_is_not_a_task_is_reported(tmp_path: Path) -> None:
    _write(tmp_path, "1.json", {"id": "1", "subject": "Fine", "status": "pending"})
    _write(tmp_path, "2.json", "{broken")
    _write(tmp_path, "3.json", "[1, 2]")
    result = load_tasks(SESSION, tmp_path)
    assert [task.id for task in result.tasks] == ["1"]
    assert result.unreadable == ["2.json", "3.json"]


def test_a_task_without_id_takes_its_file_name(tmp_path: Path) -> None:
    _write(tmp_path, "7.json", {"subject": "No id"})
    assert load_tasks(SESSION, tmp_path).tasks[0].id == "7"


def test_a_folder_that_cannot_be_listed_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path, "1.json", {"id": "1"})

    def refuse(self: Path, pattern: str) -> list[Path]:
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "glob", refuse)
    with pytest.raises(TaskReadError, match="Cannot read the tasks"):
        load_tasks(SESSION, tmp_path)


def test_a_line_names_the_task_its_state_and_what_still_blocks_it() -> None:
    done = Task("1", "Prepare", "", "completed")
    waiting = Task("2", "Build", "", "pending", ("1", "3"))
    blocker = Task("3", "Test", "", "in_progress")
    tasks = TaskList([done, waiting, blocker])
    assert tasks.line(done) == "1, Prepare, completed"
    assert tasks.line(waiting) == "2, Build, pending, blocked by 3"
    assert tasks.line(blocker) == "3, Test, in progress"


def test_an_unknown_status_is_shown_as_it_is() -> None:
    assert TaskList().line(Task("1", "x", "", "weird")) == "1, x, weird"
