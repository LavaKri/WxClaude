# Versions

How the version of WxClaude is numbered, kept and released. What each version holds is in
`CHANGELOG.md` at the root of the repository.

## The number

`MAJOR.MINOR.PATCH` (semantic versioning):

- **PATCH** (`0.1.1`): fixes, no new function.
- **MINOR** (`0.2.0`): new functions.
- **MAJOR** (`1.0.0`): the first version considered stable. While the checks by hand with NVDA and
  JAWS (`open-questions.md`) are not done, the major number stays `0`.

## Where it is written

- **One place**: `__version__` in `src/wxclaude/__init__.py`. `pyproject.toml` reads it
  (`dynamic = ["version"]`), the About dialog shows it, and `tests/test_version.py` checks that
  `pyproject.toml` resolves to the same number, that it has the `MAJOR.MINOR.PATCH` form and that
  `CHANGELOG.md` has an entry for it.
- **In git**: an annotated tag `vMAJOR.MINOR.PATCH` on the commit that sets the number.
  `push-dropbox.bat` pushes the tags with the branches.

## Releasing a version

1. Work is committed and the four checks pass (`CLAUDE.md`, "Full check").
2. The help pages are up to date: run `MakeHelp\make_help.py` for each language and commit them.
3. Change `__version__`, then write the entry of `CHANGELOG.md` (replace "not released yet" by the
   date, `YYYY-MM-DD`) and check the numbers in `roadmap.md`.
4. Run the full check again, then commit: `Version X.Y.Z`.
5. Tag it: `git tag -a vX.Y.Z -m "Version X.Y.Z"`, then run `push-dropbox.bat`.
6. The packaging (PyInstaller, a milestone of `roadmap.md`) builds from that tag and names the
   archive `WxClaude-X.Y.Z`.

Between two versions `CHANGELOG.md` keeps a section "Unreleased" on top, that is filled as the work
goes; at the release it becomes the section of the new number (the test of the version expects that
section to exist when the number is changed). The section of the current number (now `0.2.0`) is
the one that is filled until the version is tagged; after that a section "Unreleased" is added on top.
