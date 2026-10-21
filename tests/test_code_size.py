"""Size of the source files and of the classes (see ``docs/working-rules.md``).

A file may not go over ``FILE_LIMIT`` lines and a class over ``CLASS_LIMIT`` lines. What is over
the limit today is listed with its present size: it may not grow, and it comes out of the list as
soon as it is under the limit. Split before adding, never raise a ceiling.
"""

import ast
from dataclasses import dataclass, field
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SOURCE = Path(__file__).resolve().parent.parent / "src" / "wxclaude"
FILE_LIMIT = 600
CLASS_LIMIT = 300

#: Files over the limit, by path from the source folder, with the size they may not exceed.
KNOWN_LARGE_FILES = {"ui/main_window.py": 1031}
#: Classes over the limit, as "path::Name", with the size they may not exceed.
KNOWN_LARGE_CLASSES = {
    "ui/main_window.py::MainWindow": 940,
    "ui/preferences_dialog.py::PreferencesDialog": 314,
}


@dataclass(slots=True)
class Limits:
    """The limits to check and what is allowed to be over them for now."""

    file_limit: int = FILE_LIMIT
    class_limit: int = CLASS_LIMIT
    large_files: dict[str, int] = field(default_factory=dict)
    large_classes: dict[str, int] = field(default_factory=dict)


def _problem(key: str, size: int, limit: int, known: dict[str, int], what: str) -> str | None:
    """What is wrong with ``size`` for ``key``, None if nothing."""
    ceiling = known.get(key)
    if ceiling is None:
        if size > limit:
            return f"{what} {key} has {size} lines, over the limit of {limit}: split it."
        return None
    if size > ceiling:
        return f"{what} {key} grew to {size} lines, over its ceiling of {ceiling}: split it."
    if size <= limit:
        return f"{what} {key} is now {size} lines, under the limit: remove it from the known list."
    return None


def find_violations(root: Path, limits: Limits) -> list[str]:
    """The files and classes under ``root`` that break the limits, as readable messages."""
    problems: list[str | None] = []
    for path in sorted(root.rglob("*.py")):
        name = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        problems.append(
            _problem(name, len(text.splitlines()), limits.file_limit, limits.large_files, "File")
        )
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.ClassDef) and node.end_lineno is not None:
                size = node.end_lineno - node.lineno + 1
                key = f"{name}::{node.name}"
                problems.append(
                    _problem(key, size, limits.class_limit, limits.large_classes, "Class")
                )
    return [problem for problem in problems if problem is not None]


def test_the_source_respects_the_size_limits() -> None:
    limits = Limits(large_files=KNOWN_LARGE_FILES, large_classes=KNOWN_LARGE_CLASSES)
    assert find_violations(SOURCE, limits) == []


# The checker itself, on small trees made for the purpose --------------------------------------


def _write(root: Path, name: str, lines: int) -> None:
    (root / name).write_text("x = 1\n" * lines, encoding="utf-8")


def _write_class(root: Path, name: str, class_name: str, body_lines: int) -> None:
    body = "    value = 1\n" * body_lines
    (root / name).write_text(f"class {class_name}:\n{body}", encoding="utf-8")


SMALL = Limits(file_limit=10, class_limit=5)


def test_a_small_file_and_a_small_class_are_fine(tmp_path: Path) -> None:
    _write(tmp_path, "a.py", 10)
    _write_class(tmp_path, "b.py", "Small", 4)  # five lines with its header
    assert find_violations(tmp_path, SMALL) == []


def test_a_file_over_the_limit_is_reported(tmp_path: Path) -> None:
    _write(tmp_path, "a.py", 11)
    (problem,) = find_violations(tmp_path, SMALL)
    assert "File a.py has 11 lines, over the limit of 10" in problem


def test_a_class_over_the_limit_is_reported_with_its_file(tmp_path: Path) -> None:
    _write_class(tmp_path, "b.py", "Big", 5)
    (problem,) = find_violations(tmp_path, SMALL)
    assert "Class b.py::Big has 6 lines, over the limit of 5" in problem


def test_a_nested_class_counts_too(tmp_path: Path) -> None:
    body = "    class Inner:\n" + "        value = 1\n" * 5
    (tmp_path / "c.py").write_text("class Outer:\n" + body, encoding="utf-8")
    problems = find_violations(tmp_path, SMALL)
    assert any("c.py::Inner" in problem for problem in problems)


def test_folders_are_searched(tmp_path: Path) -> None:
    (tmp_path / "ui").mkdir()
    _write(tmp_path / "ui", "deep.py", 11)
    (problem,) = find_violations(tmp_path, SMALL)
    assert "ui/deep.py" in problem


def test_a_known_large_file_may_stay_but_not_grow(tmp_path: Path) -> None:
    _write(tmp_path, "a.py", 20)
    assert find_violations(tmp_path, Limits(10, 5, {"a.py": 20})) == []
    _write(tmp_path, "a.py", 21)
    (problem,) = find_violations(tmp_path, Limits(10, 5, {"a.py": 20}))
    assert "grew to 21 lines, over its ceiling of 20" in problem


def test_a_known_large_class_may_stay_but_not_grow(tmp_path: Path) -> None:
    _write_class(tmp_path, "b.py", "Big", 8)
    known = {"b.py::Big": 9}
    assert find_violations(tmp_path, Limits(10, 5, {}, known)) == []
    _write_class(tmp_path, "b.py", "Big", 9)
    (problem,) = find_violations(tmp_path, Limits(10, 5, {}, known))
    assert "grew to 10 lines, over its ceiling of 9" in problem


def test_a_known_entry_that_is_under_the_limit_must_leave_the_list(tmp_path: Path) -> None:
    _write(tmp_path, "a.py", 10)
    (problem,) = find_violations(tmp_path, Limits(10, 5, {"a.py": 20}))
    assert "is now 10 lines, under the limit: remove it from the known list" in problem


def test_the_known_lists_name_things_that_exist() -> None:
    for name in KNOWN_LARGE_FILES:
        assert (SOURCE / name).is_file(), name
    for key in KNOWN_LARGE_CLASSES:
        name, _, class_name = key.partition("::")
        tree = ast.parse((SOURCE / name).read_text(encoding="utf-8"))
        names = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        assert class_name in names, key
