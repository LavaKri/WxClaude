# Architecture

WxClaude is a wxPython desktop front end for `claude -p --output-format stream-json`.

- `core/`: logic, never imports `wx` (mypy strict).
- `ui/`: thin wx layer.
- Worker threads (CLI readers) never touch wx; they post to the UI with
  `wx.CallAfter`.
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

1. `MainWindow` builds a `RunRequest` (prompt, complete agent, conversation id, `resume` if the
   session file exists, workspace) and calls `ClaudeRunner.start`. The view shows the prompt at
   once and the window is busy (Send greyed, Interrupt active).
2. `ClaudeRunner` starts the process (`--input-format stream-json --output-format stream-json
   --permission-prompt-tool stdio`) with three threads: stdout (each line is parsed by
   `stream.parse_stream_line` into events), stderr, and a supervisor that writes the prompt as a JSON
   line to stdin, waits for the end and sends `TurnEnded`, always the last event.
3. Events reach the interface through `wx.CallAfter`. Text blocks are appended to the view;
   `progress.progress_for` turns the others into progress (status bar, and announcement if the
   option is on; the same text is not repeated).
4. At `TurnEnded`, `progress.turn_outcome` decides done / interrupted / failed. A failure is said in
   the status bar and shown in a dialog. Then the session file is read and the view is rebuilt if
   the text it would hold differs from what is shown; if it is the same, the view only takes the
   messages from the file (`adopt_details`) so that they carry their tools. `RateLimit` and
   `TurnResult` events feed the `UsageTracker`.
5. When Claude asks a permission (`PermissionRequest`), the window answers with `ClaudeRunner.allow`
   or `deny`: at once if the rule was allowed earlier in this message, else after the question
   dialog. *Always allow* writes an allow rule in `.claude/settings.local.json`
   (`claude_settings.allow_always`) and keeps it for the rest of the message; the CLI reads the file
   itself afterwards. Stdin is closed when the result line has been read.
6. Interrupt ends the process and its children (`taskkill /T`); closing the window does the same.

## Modules of `core/`

| Module | Role |
|---|---|
| `messages.py`, `session_reader.py` | `Message` (prompt or answer, with its hidden details) and the reader of the session files of the CLI. |
| `headings.py`, `conversation_document.py` | The Markdown headings and the navigation between them (UTF-16 positions); the conversation as one Markdown text with the span of each message. |
| `agents.py` | `Agent`: model, effort and permission mode (each optional); `over()` layers one on another; `DEFAULT_AGENT` is complete. Models are listed by ascending power. |
| `settings.py` | `Settings`: JSON file in the user configuration folder; only invalid or unknown values are dropped. |
| `jsonstore.py` | Reading and writing the JSON files: atomic write, `.bak` backup, damaged file set aside (`.corrupt`). |
| `workspace_state.py` | `WorkspaceState`: per workspace, the current conversation and the name and main agent of each conversation (`workspaces/<hash>.json`). |
| `shortcuts.py` | Configurable commands, shortcut notation (`Ctrl+Shift+O`), rules and conflicts. |
| `workspaces.py` | Recent workspaces (missing folders are dropped) and how a workspace is listed. |
| `claude_projects.py` | The folders Claude Code has worked in, read from `<config>/projects`. |
| `conversations.py` | Conversation identifiers (UUID, the session id of the CLI) and proposed names. |
| `announcements.py` | `Announce` messages, `AnnouncementCenter` and the message sinks. |
| `runner.py` | `ClaudeRunner`, `RunRequest`, `build_arguments`: one `claude -p` process per message, its threads. |
| `stream.py`, `events.py` | The `stream-json` lines turned into typed events. |
| `search.py` | `SearchOptions`, next / previous occurrence in a text, the line that holds an index (no wrapping). |
| `claude_settings.py` | The permission rules of the settings files of Claude Code (general, Settings, SettingsLocal): read, merged state of a tool, edit in memory, atomic write. |
| `permissions.py` | The answer to a permission question (`Decision`, `Choice`) and the text that describes a request. |
| `labels.py` | `accessible_name`: a label without its access key marker (`&Tools` gives `Tools`), used for the accessible name of the controls. |
| `list_spec.py` | `ListSpec`: what a list dialog shows (titles, labels, lines, details), data only. |
| `progress.py` | What is said while a turn runs, and how it ended. |
| `details.py` | What a message holds without displaying it: tools, tables, links (Markdown parser) and the actions of its context menu. |
| `usage.py` | `UsageTracker`: subscription gauges and tokens / cost spent, as lines of the usage dialog. |
| `tasks.py` | The tasks Claude wrote for a session (`<config>/tasks/<id>/*.json`), read only. |
| `screen_reader.py` | The outputs available for announcements (none, UI Automation). |
| `export.py` | Writes the conversation text to a file. |
| `errors.py` | `WxClaudeError` and its subclasses. |

## Modules of `ui/`

| Module | Role |
|---|---|
| `main_window.py` | Menus, prompt, buttons; the runner events, the permission questions, the focus rules (`_modal`); enables what needs a workspace or a conversation. |
| `conversation_view.py` | The read-only Markdown field: keys for the headings, search selection, `focus_last_prompt`, the context menu of a message. |
| `preferences_dialog.py`, `preferences_pages.py` | Preferences: the notebook, OK and the validation of the pages; one class per page (General, Claude, Workspace, Agent, Screen reader), each applying its own values. |
| `shortcuts_page.py` | The page to choose shortcuts, independent of the settings (commands and shortcuts are given to it); it can be copied with `core/shortcuts.py`, `shortcut_keys.py` and `fields.py`. |
| `fields.py` | `read_only_field`: the read-only multi-line field the Tab key reaches. |
| `menus.py` | Menus described as tables (`MenuEntry`: text, handler, configurable command, what it needs); `add_entries` appends and binds them. |
| `search_controller.py` | `SearchController`: Find, Find next and Find previous in the conversation view; keeps the last search. |
| `desktop.py` | The clipboard, the browser and the file explorer; each function says whether the desktop refused. |
| `workspace_settings_dialog.py` | Workspace settings: the permission rules of the `.claude` files (tab Tools). |
| `agent_panel.py`, `agent_dialog.py` | The fields of an agent, and the dialog to modify the agent of the conversation. |
| `permission_dialog.py` | The permission question of Claude. |
| `search_dialog.py` | The Find dialog (term, match case, whole words). |
| `conversation_name_dialog.py` | Name of a new, renamed or branched conversation. |
| `list_dialog.py` | `ListDialog(parent, spec, actions)`: a list of lines (from a `ListSpec`), the details of the selected one, a Close button and optional action buttons; the base of the three next dialogs. |
| `tasks_dialog.py`, `details_dialogs.py`, `usage_dialog.py` | Task list; tools used, rows of a table and links of a message; usage of Claude. |
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
