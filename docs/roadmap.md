# Roadmap

Start here in a new session. Read `CLAUDE.md` (rules), then this file, then the spec of the feature
you work on (`architecture.md`, `interface.md`, `conversation-display.md`, `focus.md`,
`claude-cli.md`, `settings.md`, `accessibility.md`). What is still to decide, to verify or to
improve is in `open-questions.md`.

## Where the project stands

WxClaude works end to end: a prompt starts `claude -p` (one process per message), the answer is
shown, the session file of the CLI is the reference for the history, the permission questions of
Claude are asked to the user (two channels, chosen in Preferences > Claude: the stdio protocol and
the HTTP hook), and the permission rules are edited in the settings files of Claude Code; the
details of a message (tools, tables, links), the task list, the plans and the usage of Claude are
shown in dialogs; a conversation can be branched and deleted; the usage dialog ends with the
statistics of the whole workspace, and a line under each answer sums up its tools. 854 tests
pass (`pytest`), plus `ruff check`, `ruff format --check` and `mypy src tests`.
The real CLI was checked by hand with the cheapest model (haiku, low effort): a message, a resumed
message, a permission question through each channel (allow, deny, the modes `plan` and `dontAsk`,
a structured question and its answer, the expiry of the hook), the allow / ask / deny rules of
`.claude/settings.local.json`, and the `rate_limit_event` and `result` lines that feed the usage
dialog. **Not yet verified with NVDA and JAWS** (to do at each milestone, see `accessibility.md`):
the new list *Interface type* and spin control of Preferences > Claude, the *Plan* dialog, the
statistics lines of *Claude usage* (numbers written short), the line that sums up the tools under
the answers with its check item, *Preferences* now in the File menu, the dialog of a table (list of the
rows, Left/Right change the column, a field gives the cell), the keys `H`, `T`, `L`, `I`, `K` and `Space` of
the conversation and their announcements, the tab *Announcements* of the Preferences, the dialog
of the structured questions of Claude (lists of check boxes, the message when a question is left
unanswered), the context menu of the prompt, the Display submenu, the button *Claude state* and its read-only field in
Preferences > Claude, the message at the start when Claude Code is not found, the plan dialog of the
mode Plan, and the key `K`; the *Sign in to Claude…* dialog (the focus on the progress while it waits,
the message at the end, the optional e-mail field).

Last work, in order (most recent first): the *Sign in to Claude…* dialog of the Tools menu; the button *Claude state* of the Preferences; the message and the status bar line when Claude Code is not found; the plan of Claude shown as such in the permission dialog; the keys
`K` / `Shift+K` between the links of the conversation; the Display submenu of the Conversation menu (the summary of
the tools and *Remove the Markdown formatting*, which takes the marks of bold and italic out of the
text); the fields of the status bar cut at 200 characters; the context menu of the prompt (Cut, Copy,
Paste, Modify the agent); the shortcut `Ctrl+Shift+A` for *Modify the agent*; the caret kept on its prompt when the view
is rebuilt after an answer; the dialog of the structured questions of Claude; the hook channel saying
until when it waits; the summary of a compaction hidden; the log file and the PyInstaller build (`build.bat`, a zip);
the dialog of a table by column; the keys `H` / `T` / `L` / `I` / `Space` of the conversation and
two announcement categories for them; the line that sums up the tools under the answers;
*Preferences* moved to the File menu, above Quit; the numbers of tokens written short; the
statistics of the workspace; branch and delete a conversation; the permission channels (`PermissionChannel`, the HTTP hook, the choice in the
Preferences, *Tools > Plan…*); the announcement categories (a destination each, Preferences >
Announcements, two sounds); the MVP structure; the names of the conversations taken from the CLI
sessions; the version setup; the help pages; and the **reading of the gauges with `/usage`** (at
startup, when a first workspace opens, and by a one-minute timer when a gauge is unknown or past its
reset time; handled like a message: send buttons and *Claude usage* greyed, silent; see
`interface.md`, "Status bar", and `claude-cli.md`). Gauge alerts are only said; the "Ready" line
of the status bar shows the 5-hour gauge, and the week from 75 %. The hidden window of the
announcements now lives under the panel, no longer under the status bar. What is left of all this
is in `open-questions.md` (hook options not tested, the `&` of the Preferences labels, the checks
with NVDA and JAWS).

The help page (F1) is written in Markdown in `MakeHelp/` (`Aide.md` French, `Help.md` English) and
turned into `src/wxclaude/help/fr.html` / `en.html` by `MakeHelp/make_help.py <source> <language>`
(run it for each language after editing a text; a test fails when a page is out of date).

## Decisions taken

- **Versions**: `MAJOR.MINOR.PATCH`, the number is `__version__` in `src/wxclaude/__init__.py`
  (read by `pyproject.toml`), a tag `vX.Y.Z` marks each release and `CHANGELOG.md` says what it holds
  (`versions.md`). The current number is `0.2.0` (`0.1.0` was never released), not tagged yet: it waits for the checks with NVDA and
  JAWS and for the packaging.
- **Model-View-Presenter, adopted progressively.** The folders stay `core/` (model) and `ui/`
  (views); `presenters/` is added. One screen at a time moves its logic into a presenter without
  wx, tested with a fake view (`architecture.md`). The first one is the sending of a message.
- **One machine only.** WxClaude runs on a single computer. No server/client split, no network, no
  JSON protocol of our own, no second executable. The runner sends typed events (dataclasses)
  straight to the interface. (If two machines are wanted one day, those events are the natural
  thing to serialize.)
- **Display**: a read-only text field holding the conversation as a Markdown document, navigation
  by headings (see `conversation-display.md`). First version: only the user's prompts and Claude's
  answers; everything else (tools, tables, links) later, in dialogs.
- **Progress**: status bar (not focusable) + UI Automation announcements; no shortcut of ours to
  read it (screen readers have one for the status bar).
- **Agents** replace the word "profile": model, effort, permission mode, always all three
  explicit for a conversation (nothing is left to the CLI settings). An alternative agent is
  used by Shift+Enter. Changing the model loses the prompt cache, the rest does not
  (`claude-cli.md`).
- **A conversation always belongs to a workspace** and has an identifier (the CLI session id,
  chosen by the application with `--session-id`). Opening a workspace (also at startup, for
  the last one) selects and loads its remembered conversation, else its most recent one, else none
  (never created automatically).
- **One process per message** (`claude -p` is started for each prompt), not one long-lived
  process. Its input is `stream-json` and stays open while Claude works.
- **Two permission channels**, chosen in Preferences > Claude and applied per message: the stdio
  control protocol (default: all the questions, plan approval) and the HTTP hook (the documented
  interface of the CLI; no structured question, no plan approval, the CLI stops waiting after
  the waiting time). A conversation can switch at any time. Details and test results in
  `claude-cli.md`, "Permission channels"; the other ways that were considered are listed there.
- **Statistics of the workspace** live in a ledger of ours, not in the files of Claude Code (a
  deleted conversation takes its totals with it, a branch holds those of its parent). The time is
  the time of work, without the user's answers to permission questions (`claude-cli.md`, "The
  stream"); there is no reset. The numbers of tokens are exact up to 999999, then `1,5 million`,
  `721 millions`, `1,2 milliard`, `12 milliards`.
- **The help is not changed unless the user asks** (`MakeHelp/` and the pages built from it).
- **One instance** of WxClaude per user; a second launch brings the first window to the front.
- **Names of conversations** are the names of the sessions, kept by the CLI: `--name` with the first
  message, `/rename` afterwards (`claude-cli.md`). WxClaude stores no name and never writes the
  session files of the CLI; it only moves them to the Recycle Bin when the user deletes a
  conversation.
- **Branch**: a branch keeps the text on screen under a new name; its first message copies the
  history of the conversation into a session of its own (`--fork-session`), the original is left
  as it is. A conversation without any message has nothing to branch.
- **Delete** moves to the Recycle Bin of Windows what Claude Code keeps of the conversation (its
  transcript, the folder beside it, its file history, its tasks), after a confirmation (No by
  default); the CLI has no command for one session (`claude-cli.md`).
- **Errors from Claude** (CLI not found or not logged in, process failure, API error such as an
  overload or a reached limit, result with an error) go to the status bar and to a dialog, never
  into the conversation text.
- **Titles**: prompts are level 1, answers level 2 (`conversation-display.md`); the wording is kept.
- **Focus and caret** follow four general rules and a few particular cases (`focus.md`).
- **Permission rules live in the settings files of Claude Code** (`.claude/settings.json`,
  `.claude/settings.local.json`; the general file is only read), not in WxClaude's own files, so the
  CLI shares them. "Always allow" writes in the personal file. The preference "Change the tools only
  in the local file" protects the versioned one.
- **Usage dialog**: `Ctrl+Shift+U`, fed by the stream (`rate_limit_event`, `result`) and by the
  reading of `/usage` (startup, one-minute timer); it never reads by itself when it opens, so it
  never waits for the CLI.
- **Details of a message** are opened from the context menu of the view, never displayed in the
  text (`conversation-display.md`); only web and mail addresses are handed to the system.
- **"Options" is named "Preferences"**; the per-workspace settings are "Workspace settings".
- **No migration** of older settings files: only the keys described in `settings.md` are read.
- **No subagents** when working on this project (see `CLAUDE.md`).
- Nothing in the code or docs may refer to another project.

## Done

1. **Conversation model and history** (`core/conversation/messages.py`, `core/claude/session_reader.py`).
2. **Display**: Markdown heading parser and navigation, `ConversationView`, resume a conversation,
   refresh (F5), hidden system messages option, search (Ctrl+F, F3, Shift+F3), the focus rules.
3. **Runner**: `claude -p` in `stream-json`, reader threads, typed events, a fake `claude` for the
   tests (`tests/fakes/fake_claude.py`), interrupt, busy state, progress announced, the session file
   read again after each turn.
4. **Permissions**: the question dialog (allow, always allow, deny with an explanation), "always
   allow" written in `.claude/settings.local.json`, and the **Workspace settings** dialog (tab Tools)
   that edits the allow / ask / deny rules of the settings files. The two permission channels
   (stdio protocol, HTTP hook) behind `PermissionChannel`, the choice and the waiting time in
   Preferences > Claude.
5. **Details dialogs** (`core/conversation/details.py`, `ui/details_dialogs.py`, context menu of
   `ConversationView`): tools used, tables, links, copy a message. **Claude usage** dialog
   (`core/claude/usage.py`, `ui/usage_dialog.py`). **Task list** read from `<config>/tasks/<id>/*.json`
   (`core/claude/tasks.py`, `ui/tasks_dialog.py`). **Plans** of a conversation, to read (`core/claude/plans.py`,
   `ui/plans_dialog.py`, *Tools > Plan…*). The dialogs share `ui/list_dialog.py`.
   The context menu of the conversation is always ours (the native one of the field is never
   shown, see `conversation-display.md`).
6. Around them: skeleton and menus, Preferences (General, Claude, Workspace, Agent, Shortcuts,
   Announcements), the Claude tab (automatic search of `claude`, or its path chosen by hand), the
   status bar with the position among the prompts (`Message 3 of 8`), configurable shortcuts, agents, conversation names, workspaces (recent, from Claude
   projects, last one reopened, one state file each), robust JSON files, single instance, UI
   Automation announcements, open the workspace folder.
7. **Code structure** (`working-rules.md`): the generic working rules, structure checks in the
   linter configuration, `tests/test_code_size.py` (warns about files over 600 lines and classes
   over 300), the Preferences split by page, the tests of the main window split by subject, and
   the main window split by composition (`Feedback`, `MainMenu`).
8. **Model-View-Presenter**: `presenters/` (no wx, mypy strict, tested with a fake view) and
   `tests/test_layers.py` (no wx in `core/` and `presenters/`). Every screen with logic has its
   presenter and its wx view: sending a message (`RunPresenter`), the current conversation
   (`ConversationPresenter`), the workspaces, the search, the details of the messages, the files,
   the announcement categories of the Preferences. `MainWindow` only builds and wires them (under
   300 lines). The files of Claude Code reach the presenters through `ClaudeFiles`, and `core/` is
   grouped by subject: `claude/`, `conversation/`, `config/`, `speech/`.
9. **Branch and delete**: a branch made with `--fork-session` at its first message, and *Delete
   the conversation*, which moves its files to the Recycle Bin. Export was already there.
10. **Statistics of the workspace**: a ledger per workspace (`workspace_stats.py`) that counts
    every finished message (messages, conversations, tokens, time of work without the waits for
    permission questions, cost, split by model) and keeps what deleted conversations used; the
    conversations that exist are counted once at the first use. Shown at the end of *Claude usage*,
    where every number of tokens is written short (`numbers.py`).
11. **Summary of the tools under the answers** (`tool_summary.py`): one line under each answer that
    used tools, shown or hidden by a check item of the Display submenu (`settings.md`,
    `show_tools_summary`). *Preferences* is in the File menu, above Quit.
12. **Log file** (`core/diagnostics.py`): `wxclaude.log` with a start-up report, the uncaught errors
    of every thread, a crash file apart; the level is set by the `.bat` shipped with the zip. **Packaging**: `build.bat` makes `dist\WxClaude` (PyInstaller, one
    folder, no console) and `dist\WxClaude-<version>.zip`, with `LICENSE` and a
    `THIRD-PARTY-NOTICES.txt` made by `packaging/make_notices.py` from `pyproject.toml` and the
    installed packages (the license of each, and its text where it ships one).
13. **Navigation of the conversation**: `H` headings, `1`-`6` levels, `T` tables, `L` lists of level 1,
    `I` items of the list the caret is in (`core/conversation/blocks.py`), `Space` shows the table
    at the caret; the announcements of the moves are two categories (*movement done*, *no further
    movement possible*). The table dialog shows one column at a time (`ui/table_dialog.py`; the first
    dialog is one assignment away, `TABLE_DIALOG`).

## Next milestones


7. **Packaging**: done for the build and the zip (item 12). Left: the icon, the tests with the real
   zip on another machine, and the manual checks with NVDA and JAWS. The unpacked zip was started on
   another Windows 11 machine without Claude Code: the application starts. Not tried yet on a machine
   with Claude Code signed in, nor with a screen reader.
8. **Signing in to Claude Code from WxClaude**: done for the subscription (*Tools > Sign in to Claude…*,
   `core/claude/auth.py`, `presenters/login_presenter.py`, `ui/login_dialog.py`; measured with the real
   CLI in an empty `CLAUDE_CONFIG_DIR`). Left, in `open-questions.md`: sign out, `--sso` and `--console`,
   the check at the start, the checks with NVDA and JAWS.
9. **Spelling dialog** for the prompt (a shortcut, a check list of corrections, an editable list of
   other choices), after choosing the spell checker.
10. **Claude Code missing**, the rest: grey the send buttons, try again, the install address.
11. **After that**, from `open-questions.md`: the tab "Environment variables" of the Workspace
   settings, the tools announced by the CLI added to the list, and the other settings of the
   `.claude` files.

## Working notes for a new session

- Commands, layout and rules are in `CLAUDE.md`. One shell command per call, never chained. The
  general working rules (structure, size, tests, texts, accessibility) are in `working-rules.md`.
- Manual tests with the real CLI use `haiku` with effort `low`; the protocol facts that were verified
  are in `claude-cli.md`.
- Every run of the CLI in a folder adds a project to `~/.claude/projects/`, and *Open from Claude
  projects* lists the projects whose folder still exists. Run the real CLI in a dedicated work
  folder, and when done delete the work folder and its entry in `~/.claude/projects/` (a test
  folder in `Temp` that is left shows up in the user's list). Never leave scripts in the project.
- The tests of the UI create real wx windows; a fake `claude` replaces the CLI everywhere in the
  tests (`FAKE_CLAUDE` scenarios, see the top of `tests/fakes/fake_claude.py`), and `CLAUDE_CONFIG_DIR`
  is redirected so that the real `~/.claude` is never read.
- The French catalog is `locale/fr/LC_MESSAGES/wxclaude.po`; recompile it with the command of
  `CLAUDE.md` after an edit.
