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
shown in dialogs. 422 tests pass (`pytest`), plus `ruff check`, `ruff format --check` and `mypy src`.
The real CLI was checked by hand with the cheapest model (haiku, low effort): a message, a resumed
message, a permission question through each channel (allow, deny, the modes `plan` and `dontAsk`,
a structured question, the expiry of the hook), the allow / ask / deny rules of
`.claude/settings.local.json`, and the `rate_limit_event` and `result` lines that feed the usage
dialog. **Not yet verified with NVDA and JAWS** (to do at each milestone, see `accessibility.md`):
the new list *Interface type* and spin control of Preferences > Claude, and the *Plan* dialog.

Last work (permission channels), in order: the channel behind `PermissionChannel`, the HTTP hook
(`core/hook_channel.py`), the choice in the Preferences, *Tools > Plan…*. What is left of it is in
`open-questions.md`: the hook options not tested yet, the `&` of the Preferences labels. The help
page (F1, Markdown in `src/wxclaude/help/`, rendered to HTML on opening) exists in French and
English and grows with the features. The announcements are grouped in categories with a
destination each (Preferences > Screen reader; two sounds, for the end of an answer and for the
question of permission).

## Decisions taken

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
- **One instance** of WxClaude per user; a second launch brings the first window to the front.
- **Names of conversations** are kept by WxClaude only; the session files of the CLI are never
  written by WxClaude.
- **Errors from Claude** (CLI not found or not logged in, process failure, API error such as an
  overload or a reached limit, result with an error) go to the status bar and to a dialog, never
  into the conversation text.
- **Titles**: prompts are level 1, answers level 2 (`conversation-display.md`); the wording is kept.
- **Focus and caret** follow four general rules and a few particular cases (`focus.md`).
- **Permission rules live in the settings files of Claude Code** (`.claude/settings.json`,
  `.claude/settings.local.json`; the general file is only read), not in WxClaude's own files, so the
  CLI shares them. "Always allow" writes in the personal file. The preference "Change the tools only
  in the local file" protects the versioned one.
- **Usage dialog**: `Ctrl+Shift+U`, fed by the stream (`rate_limit_event`, `result`), nothing is
  asked of the CLI for it.
- **Details of a message** are opened from the context menu of the view, never displayed in the
  text (`conversation-display.md`); only web and mail addresses are handed to the system.
- **"Options" is named "Preferences"**; the per-workspace settings are "Workspace settings".
- **No migration** of older settings files: only the keys described in `settings.md` are read.
- **No subagents** when working on this project (see `CLAUDE.md`).
- Nothing in the code or docs may refer to another project.

## Done

1. **Conversation model and history** (`core/messages.py`, `core/session_reader.py`).
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
5. **Details dialogs** (`core/details.py`, `ui/details_dialogs.py`, context menu of
   `ConversationView`): tools used, tables, links, copy a message. **Claude usage** dialog
   (`core/usage.py`, `ui/usage_dialog.py`). **Task list** read from `<config>/tasks/<id>/*.json`
   (`core/tasks.py`, `ui/tasks_dialog.py`). **Plans** of a conversation, to read (`core/plans.py`,
   `ui/plans_dialog.py`, *Tools > Plan…*). The dialogs share `ui/list_dialog.py`.
   The context menu of the conversation is always ours (the native one of the field is never
   shown, see `conversation-display.md`).
6. Around them: skeleton and menus, Preferences (General, Claude, Workspace, Agent, Shortcuts,
   Screen reader), the Claude tab (automatic search of `claude`, or its path chosen by hand), the
   status bar with the position among the prompts (`Message 3 of 8`), configurable shortcuts, agents, conversation names, workspaces (recent, from Claude
   projects, last one reopened, one state file each), robust JSON files, single instance, UI
   Automation announcements, open the workspace folder.
7. **Code structure** (`working-rules.md`): the generic working rules, structure checks in the
   linter configuration, `tests/test_code_size.py` (warns about files over 600 lines and classes
   over 300), the Preferences split by page, the tests of the main window split by subject, and
   the main window split by composition (`Feedback`, `MainMenu`, `SearchController`,
   `MessageActions`, `WorkspaceOpener`, `FileActions`). The conversations are
   still in `MainWindow` (see `open-questions.md`).
8. **Model-View-Presenter, first presenter**: `presenters/` (no wx, mypy strict, tested with a
   fake view), `RunPresenter` taken out of the former `RunController`, its wx view `WxRunView`,
   and `tests/test_layers.py` (no wx in `core/` and `presenters/`).

## Next milestones

0. **Model-View-Presenter, the other screens**, one at a time, tests green at each step: the
   workspaces (`WorkspaceOpener`), the search (`SearchController`), the actions on the messages
   (`MessageActions`, `FileActions`), the Screen reader page, then `MainWindow`, which should go
   back under 300 lines.

6. **Rename, branch (`--fork-session`), delete**, export. Rename and branch exist but are
   provisional: a rename only changes the name kept by WxClaude, a branch only starts a new
   conversation identifier with the text still on screen. Delete is greyed.
7. **Packaging** (PyInstaller; the translations `.mo` and `data/tools.txt` are package data) and
   manual checks with NVDA and JAWS.
8. **After that**, from `open-questions.md`: the tab "Environment variables" of the Workspace
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
