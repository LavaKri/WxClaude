# WxClaude

A desktop front end for [Claude Code](https://claude.com/claude-code), made to be used with a screen
reader. It runs the Claude Code command line in its non-interactive mode (`claude -p`) and shows the
conversation in native Windows controls, so that NVDA and JAWS can read everything and every
function is reachable by keyboard.

Status: version 0.2.0. The application works from end to end, but the checks by hand with NVDA and
JAWS are not finished, so the version number stays below 1.0. See `CHANGELOG.md`.

## What it does

- Sends messages to Claude Code and shows the answers in a read-only conversation, with keys to move
  by heading, table, list and link.
- Asks the permission questions of Claude in dialogs, and edits the permission rules of a workspace.
- Keeps the conversations of Claude Code (resume, branch, delete) and shows the usage of the
  subscription and the statistics of a workspace.
- Signs in to Claude Code from a dialog (*Tools > Sign in to Claude…*), without a terminal.
- French and English interface (French by default), configurable shortcuts and announcements.

## Requirements

- Windows 11.
- Python 3.14 and wxPython 4.3.
- Claude Code installed and reachable as `claude` (or its path given in *File > Preferences >
  Claude*), and a Claude account to sign in with.

## Install and run

From the root of the repository, in PowerShell:

```
python -m venv .venv --system-site-packages
.venv\Scripts\python.exe -m pip install -e .[dev]
wxclaude.bat
```

The virtual environment uses the wxPython of the base installation (`--system-site-packages`).
`build.bat` makes a folder `dist\WxClaude` and a zip with PyInstaller.

## Checks

Four separate commands:

```
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check
.venv\Scripts\python.exe -m ruff format --check
.venv\Scripts\python.exe -m mypy src tests
```

## Documentation

The specifications are in `docs/` (English): `roadmap.md` is the place to start, then the topic
you need (`architecture.md`, `interface.md`, `settings.md`, `accessibility.md`, `claude-cli.md`).
The help of the application is written in `MakeHelp/`.

## Contributing

The project does not accept contributions. See `CONTRIBUTING.md`.

## License

WxClaude is free software, published under the GNU General Public License, version 3 only
(`GPL-3.0-only`). You may use, study, change and share it, and when you share it, with or without
changes, you must give the same rights on the whole work and its source. The full text is in
`LICENSE`. There is no warranty.

### Third-party software

WxClaude uses the software below, each under its own license (read from their metadata):

- [wxPython](https://wxpython.org/) 4.3: wxWindows Library License.
- [platformdirs](https://github.com/tox-dev/platformdirs): MIT.
- [markdown-it-py](https://github.com/executablebooks/markdown-it-py) and its dependency
  [mdurl](https://github.com/executablebooks/mdurl): MIT.

They are installed from their own sources with `pip`, they are not part of this repository. The
packaged application (`build.bat`, a folder and a zip) carries them, with the runtime of Python and
its native libraries (OpenSSL, libffi, Expat, the Microsoft Visual C++ runtime): the file
`THIRD-PARTY-NOTICES.txt` in the folder gives the license of each and the text of the ones that
ship one. The development tools (ruff, mypy, pytest, Babel, PyInstaller) are not distributed.
