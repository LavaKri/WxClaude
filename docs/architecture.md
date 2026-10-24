# Architecture

WxClaude is a wxPython desktop front end for `claude -p --output-format stream-json`.

The code follows Model-View-Presenter, moved to it one screen at a time:

- `core/`: the model (logic, files, the CLI), never imports `wx` (mypy strict).
- `presenters/`: the logic of a screen, never imports `wx` (mypy strict). A presenter talks to its
  view only through a `Protocol` and is tested with a fake view, without a window.
- `ui/`: the wx views: windows, dialogs, controls, and the classes that implement the `Protocol` of
  a presenter. The screens that have no presenter yet keep their logic here.
- `tests/test_layers.py` checks that `core/` and `presenters/` never import `wx`; `tests/test_version.py`
  checks the version (`versions.md`).
- The files of Claude Code (sessions, tasks, plans, projects, "always allow" rules) reach the
  presenters through one contract, `ClaudeFiles` (`core/claude/claude_files.py`): `DiskClaudeFiles` is
  the real one, tested on disk in `tests/core/`; the tests of the presenters use
  `tests/presenters/fake_claude_files.py`, in memory. WxClaude's own files (settings, workspace
  state) stay with `Settings` and `WorkspaceState`.
- Worker threads (CLI readers) never touch wx; they hand their events to the view, which posts
  them to the UI with `wx.CallAfter`.
- The rules of structure and size of the code are in `working-rules.md`.

## Scope

WxClaude runs on **one machine**: there is no server/client split, no network and no protocol of
our own. The runner sends typed events (dataclasses) straight to the interface, through
`wx.CallAfter`. The CLI's session file stays the reference for what was said.

## Current state

The conversation model, the display, the runner and the permissions exist: a prompt starts
`claude -p` (one process per message), the answer appears block by block, Claude's permission
questions are asked to the user, and the session file of the CLI is read again at the end of the
turn. The permission rules are edited in the settings files of Claude Code. The plan, in order, is
in `roadmap.md`. What is known about the CLI is in `claude-cli.md`.

## A turn

1. `RunPresenter` (`presenters/run_presenter.py`, its view `WxRunView` in `ui/run_view.py`)
   builds a `RunRequest` (prompt, complete agent, conversation id, `resume` if the
   session file exists, workspace) and calls `ClaudeRunner.start`. The view shows the prompt at
   once and the window is busy (Send greyed, Interrupt active).
2. `ClaudeRunner` starts the process (`--input-format stream-json --output-format stream-json`
   plus the arguments of its permission channel, `--permission-prompt-tool stdio` for
   `StdioChannel`) with three threads: stdout (each line is parsed by
   `stream.parse_stream_line` into events), stderr, and a supervisor that writes the prompt as a JSON
   line to stdin, waits for the end and sends `TurnEnded`, always the last event.
3. Events reach the presenter on the interface thread through `RunView.call_after`
   (`wx.CallAfter`). Text blocks are appended to the view;
   `progress.progress_for` turns the others into progress (announced where the category "Progress
   of Claude" says; the same text is not repeated).
4. At `TurnEnded`, `progress.turn_outcome` decides done / interrupted / failed. A failure is said in
   the status bar and shown in a dialog. Then the session file is read and the view is rebuilt if
   the text it would hold differs from what is shown; if it is the same, the view only takes the
   messages from the file (`adopt_details`) so that they carry their tools. `RateLimit` and
   `TurnResult` events feed the `UsageTracker`.
5. When Claude asks a permission (`PermissionRequest`), the controller answers with `ClaudeRunner.allow`
   or `deny`: at once if the rule was allowed earlier in this message, else after the question
   dialog. *Always allow* writes an allow rule in `.claude/settings.local.json`
   (`claude_settings.allow_always`) and keeps it for the rest of the message; the CLI reads the file
   itself afterwards. Stdin is closed when the result line has been read.
6. Interrupt ends the process and its children (`taskkill /T`); closing the window does the same.

## Modules of `core/`

Grouped by subject (`working-rules.md`: split by subject, not by technical kind).

### `core/claude/`: Claude Code (the CLI, its stream, its permission channels, its files)

| Module | Role |
|---|---|
| `claude_projects.py` | The folders Claude Code has worked in, read from `<config>/projects`; the files of a session (what deleting it removes). |
| `session_reader.py` | The reader of the session files of the CLI: the messages, the last agent, the usage, the totals of the session and its first time. |
| `cost_state.py` | `CostState`, `ModelTotals`: the totals the CLI keeps of a session (`cost-state` entries): cost, time of work, tokens and cost of each model. |
| `stats_import.py` | `import_sessions`: counts the conversations that exist when the statistics of a workspace start; a branch is counted from where it leaves its conversation. |
| `claude_files.py` | `ClaudeFiles` (Protocol): what the presenters read and write of the files of Claude Code; `DiskClaudeFiles`, the real one, built on the modules above. |
| `runner.py` | `ClaudeRunner`, `RunRequest`, `build_arguments`: one `claude -p` process per message, its threads; also the rename of a session and the reading of the gauges (`read_usage`, `/usage`, stopped after 15 seconds), which share its single process. |
| `permission_channel.py` | `PermissionChannel` (Protocol): how the CLI asks a permission and how the answer goes back, one channel per message; `StdioChannel` (control protocol on stdin / stdout), `make_channel` (`stdio` or `hook`). See `claude-cli.md`, "Permission channels". |
| `hook_channel.py` | `HookChannel`: a server on `127.0.0.1` (one per message, a token in the URL) that receives the POST of the CLI's `PermissionRequest` hook, hands it to the interface as a `PermissionRequest` event and writes the response from its own thread; the interface thread only stores the decision. A question nobody answers gives `PermissionExpired`. |
| `process_input.py` | `ProcessInput`: the JSON lines written to the standard input of the process, from several threads, closed once. |
| `stream.py`, `events.py` | The `stream-json` lines turned into typed events. |
| `claude_settings.py` | The permission rules of the settings files of Claude Code (general, Settings, SettingsLocal): read, merged state of a tool, edit in memory, atomic write. |
| `permissions.py` | The answer to a permission question (`Decision`, `Choice`) and the text that describes a request. |
| `progress.py` | What is said while a turn runs, and how it ended. |
| `usage.py` | `UsageTracker`: subscription gauges and tokens / cost spent, as lines of the usage dialog. |
| `usage_text.py` | `parse_usage`: the text answered by `/usage` read as the 5-hour and weekly gauges (a text not understood gives none). |
| `gauge_schedule.py` | `GaugeSchedule`: when the gauges are read again with `/usage` (unknown, or a reset time is past) and how long to wait after a failure. |
| `tasks.py` | The tasks Claude wrote for a session (`<config>/tasks/<id>/*.json`), read only. |
| `plans.py` | The plans of a conversation: the `Write` calls of its session file to `<config>/plans/`, with their text (from the file, else from the session), read only. |

### `core/conversation/`: the conversation (messages, document, details, search, export)

| Module | Role |
|---|---|
| `messages.py` | `Message`: a prompt or an answer, with its hidden details (tools, thinking, usage). |
| `blocks.py` | The tables, the lists of level 1 and their items of a Markdown text, and the next / previous one from a position. |
| `headings.py`, `conversation_document.py` | The Markdown headings and the navigation between them (UTF-16 positions); the conversation as one Markdown text with the span of each message. |
| `conversations.py` | Conversation identifiers (UUID, the session id of the CLI) and proposed names. |
| `search.py` | `SearchOptions`, next / previous occurrence in a text, the line that holds an index (no wrapping). |
| `tool_summary.py` | `summarize_tools`: the line under an answer that sums up its tools (commands run, files modified and read, other tools, failures). |
| `details.py` | What a message holds without displaying it: tools, tables, links (Markdown parser) and the actions of its context menu. |
| `export.py` | Writes the conversation text to a file. |

### `core/config/`: WxClaude's settings (agents, shortcuts, settings file, workspaces)

| Module | Role |
|---|---|
| `agents.py` | `Agent`: model, effort and permission mode (each optional); `over()` layers one on another; `DEFAULT_AGENT` is complete. Models are listed by ascending power. |
| `settings.py` | `Settings`: JSON file in the user configuration folder; only invalid or unknown values are dropped. |
| `jsonstore.py` | Reading and writing the JSON files: atomic write, `.bak` backup, damaged file set aside (`.corrupt`). |
| `workspace_state.py` | `WorkspaceState`: per workspace, the current conversation and the name and main agent of each conversation (`workspaces/<hash>.json`). |
| `workspace_stats.py` | `WorkspaceStats`: per workspace, the ledger of what all its conversations used, deleted ones included (`workspaces/<hash>.stats.json`), and the lines that show it. |
| `shortcuts.py` | Configurable commands, shortcut notation (`Ctrl+Shift+O`), rules and conflicts. |
| `workspaces.py` | Recent workspaces (missing folders are dropped) and how a workspace is listed. |

### `core/speech/`: what is said (announcements, screen reader outputs, sounds)

| Module | Role |
|---|---|
| `announcements.py` | `Announce` messages, their `Category` and the `Destination` chosen per category, `AnnouncementCenter`, the message sinks and the sound players. |
| `sounds.py` | `WinsoundPlayer`: plays the two WAV files of `wxclaude/sounds` (Message.wav, Permission.wav). |
| `screen_reader.py` | The outputs available for announcements (none, UI Automation). |

### `core/`: shared by all

| Module | Role |
|---|---|
| `labels.py` | `accessible_name`: a label without its access key marker (`&Tools` gives `Tools`), used for the accessible name of the controls. |
| `numbers.py` | `format_tokens`: a number of tokens written exact up to 999999, then rounded (`1,5 million`, `721 millions`, `12 milliards`), with the decimal mark and the plural of the language. |
| `list_spec.py` | `ListSpec`: what a list dialog shows (titles, labels, lines, details), data only. |
| `diagnostics.py` | The log file: set-up, start-up report, uncaught errors of every thread and native crashes. |
| `errors.py` | `WxClaudeError` and its subclasses. |
| `help.py` | `help_page`: the HTML help page of a language in `wxclaude/help` (English as fallback), opened as it is by the browser. |

## Modules of `presenters/`

| Module | Role |
|---|---|
| `shared.py` | `Shared`: what the presenters of the window work on together (settings, usage of Claude, `ClaudeFiles`). |
| `run_presenter.py` | `RunPresenter`: a message sent to Claude (start, events, permission questions, progress, steps, end, interrupt) and the reading of the gauges (`refresh_gauges_if_due`, handled like a message: busy, silent), linked to the window by `RunLinks`; `RunView` is what it asks of the interface. |
| `conversation_presenter.py` | `ConversationPresenter`: the current conversation (identifier, name, main agent) and the commands of the Conversation menu (new, resume, refresh, rename, branch, agent); the title of the window (the name of a conversation is the one of its session: `--name`, `/rename`); what is remembered in the workspace file (current conversation, main agent). |
| `stats_recorder.py` | `StatsRecorder`: adds each finished message to the statistics of the workspace, without the time the user took to answer the permission questions. |
| `workspace_presenter.py` | `WorkspacePresenter`: the current workspace, what is remembered about it and its statistics (counted from the existing conversations at the first use); open a folder, a Claude project, a recent workspace, the last one at startup. The window does what follows (`WorkspaceLinks`). |
| `search_presenter.py` | `SearchPresenter`: Find, Find next and Find previous in the conversation; keeps the last search. |
| `message_presenter.py` | `MessagePresenter`: the details of a message (tools, table, links), copying it or its exchange, the task list, the plans and the usage of Claude with the statistics of the workspace. |
| `file_presenter.py` | `FilePresenter`: export the conversation, show the workspace folder in the file explorer, the help page, About. |
| `announcements_presenter.py` | `AnnouncementsPresenter`: the destination of each category of announcements, edited in the Announcements page until OK. |

## Modules of `ui/`

| Module | Role |
|---|---|
| `main_window.py` | The conversation view, the prompt and the buttons, the menus, and the wiring of the presenters and their views. |
| `conversation_screen.py` | `WxConversationScreen`: the view of `ConversationPresenter` (conversation view, prompt, title, name and agent dialogs, the confirmation and the Recycle Bin of a deletion). |
| `run_view.py` | `WxRunView`: the view of `RunPresenter` (conversation view, status bar, permission dialog, `wx.CallAfter`). |
| `gauge_watch.py` | `GaugeWatch`: the one-minute timer that asks whether the gauges are to be read (started by the application, not by the window). |
| `feedback.py` | `Feedback`: the status bar (position, messages), the announcements, and every dialog of the window through `modal`, which puts the focus back (`focus.md`); also `choose` (pick in a list), `confirm` (Yes / No, No by default) and `read_session` (the error is shown). |
| `workspace_view.py` | `WxWorkspaceView`: the view of `WorkspacePresenter` (folder dialog, messages). |
| `file_view.py` | `WxFileView`: the view of `FilePresenter` (export dialog, file explorer, browser, About). |
| `conversation_view.py` | The read-only Markdown field: keys for the headings, tables, lists and items, search selection, `focus_last_prompt`, `replace_messages` (rebuild the text, the caret staying on its message), the
line that sums up the tools, the context menu of a message. |
| `preferences_dialog.py`, `preferences_pages.py` | Preferences: the notebook, OK and the validation of the pages; one class per page (General, Claude, Workspace, Agent, Announcements), each applying its own values. |
| `shortcuts_page.py` | The page to choose shortcuts, independent of the settings (commands and shortcuts are given to it); it can be copied with `core/config/shortcuts.py`, `shortcut_keys.py` and `fields.py`. |
| `fields.py` | `read_only_field`: the read-only multi-line field the Tab key reaches. |
| `menus.py` | Menus described as tables (`MenuEntry`: text, handler, configurable command, what it needs, check item); `add_entries` appends and binds them. |
| `main_menu.py` | `MainMenu`: the menu bar of the main window (tables, recent workspaces, shortcuts, greying), told what each item does by `MenuHandlers`. |
| `message_view.py` | `WxMessageView`: the view of `MessagePresenter` (dialogs of the details, tasks, plans and usage; clipboard, browser). |
| `search_view.py` | `WxSearchView`: the view of `SearchPresenter` (Find dialog, selection in the conversation view). |
| `desktop.py` | The clipboard, the browser, the file explorer and the Recycle Bin (`SHFileOperationW`); each function says whether the desktop refused. |
| `workspace_settings_dialog.py` | Workspace settings: the permission rules of the `.claude` files (tab Tools). |
| `agent_panel.py`, `agent_dialog.py` | The fields of an agent, and the dialog to modify the agent of the conversation. |
| `permission_dialog.py` | The permission question of Claude. |
| `question_dialog.py` | `QuestionDialog`: the structured questions of Claude (`core/claude/questions.py`), a list of choices and a field of one's own per question. |
| `search_dialog.py` | The Find dialog (term, match case, whole words). |
| `conversation_name_dialog.py` | Name of a new, renamed or branched conversation. |
| `list_dialog.py` | `ListDialog(parent, spec, actions)`: a list of lines (from a `ListSpec`), the details of the selected one, a Close button and optional action buttons; the base of the three next dialogs. |
| `table_dialog.py` | `TableCellsDialog`: a table shown one column at a time (a list of the rows, Left/Right change the column, a field holds the cell), used by `message_view.TABLE_DIALOG`; the old `TableDialog` of `details_dialogs.py` (one sentence per row) comes back by changing that one line. |
| `tasks_dialog.py`, `plans_dialog.py`, `details_dialogs.py`, `usage_dialog.py` | Task list; plans; tools used, rows of a table and links of a message; usage of Claude. |
| `shortcut_keys.py` | wx key events to the shortcut notation. |
| `message_sinks.py`, `uia_provider.py` | Announcements sent as UI Automation notifications (`ctypes`). |
| `wx_locale.py` | Language of wx's own texts. |
| `single_instance.py` | Only one WxClaude per user (`wx.SingleInstanceChecker`); a second launch brings the first window to the front. |

## Workspaces and conversations

A conversation always belongs to a workspace (the working folder of the CLI). Without a workspace
there is no conversation. A file per workspace remembers its current conversation, and per
conversation its name and its main agent (`docs/settings.md`).

Whenever a workspace is opened (at startup, with the option "At startup, open the last workspace",
or later) a conversation is selected and loaded: the remembered one if its session file still
exists, else the most recent one (by its last message). A workspace without any session gets no
conversation, none is created. Opening the workspace that is already open changes nothing.

The agent of a conversation is always complete: the remembered one (over the default agent for
what it leaves unset). A conversation unknown to WxClaude takes the model, the effort and the
permission mode of its last message as its main agent, and is remembered from then on. Refreshing the conversation
(F5) reads its session file again and never touches the agent.

## Data files

`src/wxclaude/data/tools.txt` lists the tools of Claude Code (one name per line) for the Workspace
settings; it is package data. The settings files of WxClaude and of Claude Code are described in
`settings.md`.

## Translations

Message ids are English, the catalog is `locale/fr/LC_MESSAGES/wxclaude.po` (recompile with Babel,
see `CLAUDE.md`). Sentences are never concatenated: `str.format` with named fields.
