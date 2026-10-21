"""Size of the source files and of the classes (see ``docs/working-rules.md``).

A file over ``FILE_LIMIT`` lines or a class over ``CLASS_LIMIT`` lines gives a warning at every
run, not a failure: a file that is too big is not a bug, and the user decides whether to split it.
The limits are absolute: there is no list of exceptions.
"""

import ast
import warnings
from dataclasses import dataclass
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SOURCE = Path(__file__).resolve().parent.parent / "src" / "wxclaude"
FILE_LIMIT = 600
CLASS_LIMIT = 300


class CodeSizeWarning(UserWarning):
    """A file or a class is over its size limit (to be reported to the user, not to be fixed)."""


@dataclass(slots=True)
class Limits:
    """The largest size of a file and of a class, in lines."""

    file_limit: int = FILE_LIMIT
    class_limit: int = CLASS_LIMIT


def find_violations(root: Path, limits: Limits) -> list[str]:
    """The files and classes under ``root`` over the limits, as readable messages."""
    problems: list[str] = []
    for path in sorted(root.rglob("*.py")):
        name = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        lines = len(text.splitlines())
        if lines > limits.file_limit:
            problems.append(
                f"File {name} has {lines} lines, over the limit of {limits.file_limit}."
            )
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.ClassDef) and node.end_lineno is not None:
                size = node.end_lineno - node.lineno + 1
                if size > limits.class_limit:
                    problems.append(
                        f"Class {name}::{node.name} has {size} lines, "
                        f"over the limit of {limits.class_limit}."
                    )
    return problems


def warn_about_violations(root: Path, limits: Limits) -> None:
    """Raise one ``CodeSizeWarning`` for each problem found under ``root``."""
    for problem in find_violations(root, limits):
        warnings.warn(problem, CodeSizeWarning, stacklevel=2)


def test_the_source_size_limits() -> None:
    """Warns, never fails: see the warnings summary at the end of the run."""
    warn_about_violations(SOURCE, Limits())


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
    assert problem == "File a.py has 11 lines, over the limit of 10."


def test_a_class_over_the_limit_is_reported_with_its_file(tmp_path: Path) -> None:
    _write_class(tmp_path, "b.py", "Big", 5)
    (problem,) = find_violations(tmp_path, SMALL)
    assert problem == "Class b.py::Big has 6 lines, over the limit of 5."


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


def test_a_problem_is_a_warning_and_not_a_failure(tmp_path: Path) -> None:
    _write(tmp_path, "a.py", 11)
    with pytest.warns(CodeSizeWarning, match="File a.py has 11 lines"):
        warn_about_violations(tmp_path, SMALL)


def test_nothing_to_report_gives_no_warning(tmp_path: Path) -> None:
    _write(tmp_path, "a.py", 10)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        warn_about_violations(tmp_path, SMALL)
