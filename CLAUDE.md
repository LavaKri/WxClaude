# WxClaude

Screen-reader-friendly desktop front end (wxPython) for the Claude Code CLI in non-interactive
mode (`claude -p --output-format stream-json`).

This project is self-contained: it must not reference, import or depend on any other project.

Detailed specs live in `docs/` (English). The general working rules (structure and size of the code,
what to do when a check says the code is too big, tests, texts, accessibility) are in
`docs/working-rules.md`: read them before writing code. Read the relevant spec before changing a feature.
**New session: start with `docs/roadmap.md`** (decisions taken, what is done, next milestones). Open questions and improvements
are only in `docs/open-questions.md`; the other docs hold what is true, not questions.

## Stack
- Python 3.14, wxPython 4.3 (native controls, for screen reader support), platformdirs.
- Dev tools: ruff, mypy, pytest, Babel (gettext), PyInstaller.
- No uv. Virtual environment: `.venv/` (created with `--system-site-packages`, wxPython comes from the base install).

## Commands (PowerShell, from repo root)
- Setup (once): `python -m venv .venv --system-site-packages`, then `.venv\Scripts\python.exe -m pip install -e .[dev]`
- Run: `wxclaude.bat` (or `.venv\Scripts\python.exe -m wxclaude`)
- Translations: message ids are English, catalog in `src/wxclaude/locale/fr/LC_MESSAGES/wxclaude.po`; after editing, recompile: `.venv\Scripts\python.exe -m babel.messages.frontend compile -D wxclaude -d src/wxclaude/locale -l fr`
- Tests (targeted first): `.venv\Scripts\python.exe -m pytest tests/core/claude/test_x.py`, `-k name`, `-m unit`, `--lf`
- Full check, as four separate commands (never chained): `.venv\Scripts\python.exe -m pytest`, then `.venv\Scripts\python.exe -m ruff check`, `.venv\Scripts\python.exe -m ruff format --check`, `.venv\Scripts\python.exe -m mypy src`

## Layout
Model-View-Presenter, adopted one screen at a time (see `docs/architecture.md`):
- `src/wxclaude/core/`: the model: logic, files, CLI runner. **Never imports `wx`.** Grouped by subject: `claude/` (the CLI and its files), `conversation/`, `config/` (WxClaude's settings), `speech/` (announcements, sounds); `errors.py`, `labels.py`, `list_spec.py`, `help.py` at the root.
- `MakeHelp/`: the help text (`Aide.md`) and `make_help.py`, which turns it into `src/wxclaude/help/<language>.html` (see `docs/interface.md`, Help).
- `src/wxclaude/presenters/`: the logic of a screen. **Never imports `wx`.** Talks to its view through a `Protocol`; tested with a fake view.
- `src/wxclaude/ui/`: wx windows, dialogs and the views of the presenters; thin, no business logic.
- `tests/` mirrors `src/wxclaude/` (`tests/core/`, `tests/presenters/`, `tests/ui/`). Markers: `unit`, `ui`, `slow`.
- `docs/`: specifications, one file per topic (architecture, interface, settings, accessibility, focus). Update them when behaviour changes.

## Rules
- **Never commit without asking the user first.** Propose the message and wait for approval.
- **Never use subagents** (no Agent tool, no Explore/Plan agents): do all the research and work directly with the other tools.
- **Never chain shell commands.** One command per tool call: no `;`, `&&`, `||`, `&`, no pipes used to string commands together, no `cd x && ...`. Run independent commands as parallel tool calls and dependent ones one after the other.
- Code, comments, docstrings, specs: English. UI default language: French; every visible string goes through `_()`; no string concatenation (use `str.format` with named fields).
- Full type annotations; mypy strict on `core/` and `presenters/`. `@dataclass(slots=True)`, `Protocol` for contracts, `pathlib.Path`, explicit file encodings.
- Specific exceptions derived from `WxClaudeError`; never a bare `except` or a swallowed error. User-facing errors are announced.
- Ruff (line length 100), mypy and pytest must pass before proposing a commit.
- Run only the tests you need while working; the full suite, ruff and mypy run once, just before proposing a commit.
- Only the main thread touches wx: worker threads (CLI reader, hook server) post to the UI with `wx.CallAfter`.
- For manual tests with the real CLI, use the cheapest model and effort (`haiku`, or `sonnet` with `low`).

## Accessibility (non-negotiable)
- Everything usable by keyboard alone; accessible name on every control; defined initial focus in every dialog.
- No unexpected focus changes (the conversation view never steals focus), no information conveyed by color alone.
- Native first: rely on native controls, status bar and message dialogs. Extra speech only through an announcement center (UI Automation notifications on Windows; no MSAA, no vendor-specific API).
- Verified manually with NVDA and JAWS each milestone.
