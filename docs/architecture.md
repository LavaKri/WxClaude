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
- The fakes shared by the tests (`fake_claude.py`, `fake_vault.py`, `fake_security_view.py`) are in
  `tests/fakes/`, on the import path of pytest and mypy.
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
| `status.py` | `read_status` / `describe_status`: found or not, version and connection of Claude Code, asked of the program (`--version`, `auth status`); `read_login`: only the connection, for the check at the start (run in a thread). |
| `auth.py` | `ClaudeLogin`: `claude auth login --claudeai` with no console and its input closed, in a thread; the events `LoginUrl` (the address the CLI prints) and `LoginEnded` (success, cancelled, what it printed); `cancel` ends the process and its children. |
| `claude_projects.py` | The folders Claude Code has worked in, read from `<config>/projects`; the files of a session (what deleting it removes). |
| `session_reader.py` | The reader of the session files of the CLI: the messages, the last agent, the usage, the totals of the session and its first time. |
| `cost_state.py` | `CostState`, `ModelTotals`: the totals the CLI keeps of a session (`cost-state` entries): cost, time of work, tokens and cost of each model. |
| `stats_import.py` | `import_sessions`: counts the conversations that exist when the statistics of a workspace start; a branch is counted from where it leaves its conversation. |
| `claude_files.py` | `ClaudeFiles` (Protocol): what the presenters read and write of the files of Claude Code; `DiskClaudeFiles`, the real one, built on the modules above. |
| `runner.py` | `ClaudeRunner`, `RunRequest`, `build_arguments`: one `claude -p` process per message, its threads; also the rename of a session and the reading of the gauges (`read_usage`, `/usage`, stopped after 15 seconds), which share its single process. A request can be `restricted` (folder not approved) and carry a `ProviderLaunch`; the rename and the gauges take `restricted=` too. |
| `inline_settings.py` | `merge_settings`, `settings_arguments`: the one `--settings` of a launch, merged from the permission channel, the provider and the restriction (the CLI keeps only the last `--settings` it is given). |
| `launch.py` | What a provider adds to a launch (`providers.md`): `ProviderLaunch` (provider, key hidden from `repr`, scrub), `provider_settings` (address and aliases), `provider_environment` (key as `ANTHROPIC_AUTH_TOKEN`, inherited `ANTHROPIC_*` / `CLAUDE_CODE_USE_*` removed, telemetry off, scrub), `sends_effort`, `launch_for` (the launch of an agent; decrypts the key for this launch only). |
| `permission_channel.py` | `PermissionChannel` (Protocol): how the CLI asks a permission and how the answer goes back, one channel per message (`arguments()` for its flags, `settings()` for what it adds to the inline settings); `StdioChannel` (control protocol on stdin / stdout), `make_channel` (`stdio` or `hook`). See `claude-cli.md`, "Permission channels". |
| `hook_channel.py` | `HookChannel`: a server on `127.0.0.1` (one per message, a token in the URL) that receives the POST of the CLI's `PermissionRequest` hook, hands it to the interface as a `PermissionRequest` event and writes the response from its own thread; the interface thread only stores the decision. A question nobody answers gives `PermissionExpired`. |
| `process_input.py` | `ProcessInput`: the JSON lines written to the standard input of the process, from several threads, closed once. |
| `stream.py`, `events.py` | The `stream-json` lines turned into typed events. |
| `claude_settings.py` | The permission rules of the settings files of Claude Code (general, Settings, SettingsLocal): read, merged state of a tool, edit in memory, atomic write, through a `FileGuard` (`WatchedFiles`) when there is one. |
| `env_vars.py` | The `env` key of those files: the described variables (`data/env_vars.txt`) and those a file holds, set / remove in memory, the variables of the provider never offered. |
| `permissions.py` | The answer to a permission question (`Decision`, `Choice`) and the text that describes a request. |
| `progress.py` | What is said while a turn runs, and how it ended (the notice `unrecognized_model` of the CLI is not taken for the cause of a failure). |
| `usage.py` | `UsageTracker`: subscription gauges (`gauge_lines`) and tokens / cost spent (`statistics_lines`), as lines of the dialogs. |
| `usage_text.py` | `parse_usage`: the text answered by `/usage` read as the 5-hour and weekly gauges (a text not understood gives none). |
| `gauge_schedule.py` | `GaugeSchedule`: when the gauges are read again with `/usage` (unknown, or a reset time is past) and how long to wait after a failure. |
| `tasks.py` | The tasks Claude wrote for a session (`<config>/tasks/<id>/*.json`), read only. |
| `plans.py` | The plans of a conversation: the `Write` calls of its session file to `<config>/plans/`, with their text (from the file, else from the session), read only. |

### `core/conversation/`: the conversation (messages, document, details, search, export)

| Module | Role |
|---|---|
| `messages.py` | `Message`: a prompt or an answer, with its hidden details (tools, thinking, usage). |
| `blocks.py` | The tables, the lists of level 1 and their items of a Markdown text, and the next / previous one from a position. |
| `links.py`, `code_blocks.py` | `link_places`: the links of a text and where they start (line by line, code left out); `lines_with_code_mark`: the lines of a text with a mark on those of fenced code blocks (shared with `emphasis.py`). |
| `emphasis.py` | `remove_emphasis`: a text without the marks of bold and italic, same lines (CommonMark rules, through `markdown-it-py`). |
| `caret_anchor.py` | `CaretAnchor`: where the caret goes when the text is rebuilt (same message, same place in it, or the end). Noted before the rebuild (`take`), found after it (`position`). |
| `headings.py`, `conversation_document.py` | The Markdown headings and the navigation between them (UTF-16 positions); the conversation as one Markdown text with the span of each message. |
| `conversations.py` | Conversation identifiers (UUID, the session id of the CLI) and proposed names. |
| `search.py` | `SearchOptions`, next / previous occurrence in a text, the line that holds an index (no wrapping). |
| `tool_summary.py` | `summarize_tools`: the line under an answer that sums up its tools (commands run, files modified and read, other tools, failures). |
| `details.py` | What a message holds without displaying it: tools, tables, links (Markdown parser) and the actions of its context menu. |
| `export.py` | Writes the conversation text to a file. |

### `core/config/`: WxClaude's settings (agents, shortcuts, settings file, workspaces)

| Module | Role |
|---|---|
| `agents.py` | `Agent`: provider, model, effort and permission mode (each optional); `over()` layers one on another; `DEFAULT_AGENT` is complete (provider `claude`). Models are listed by ascending power. |
| `key_transmission.py` | The three ways the key reaches the CLI (*Masked*, *Shared*, *Relayed*), their labels and explanations, and the reading of the old setting `scrub_credentials`. |
| `provider_methods.py` | How to ask a provider for its models and its credit: the base class `ProviderMethod` (the call, the key as a bearer token, the failures), `ModelsMethod` (`V1Models`) and `CreditMethod` (`DeepSeekCredit`) with the registries `MODELS_METHODS` and `CREDIT_METHODS`; a method gives paths only, so the key goes to the host the user typed; `ModelListError` and `BalanceError` with a message for the user, never holding the key. |
| `provider_variables.py` | The closed list of the variables of the CLI a provider can set (`API_TIMEOUT_MS`, `CLAUDE_CODE_MAX_CONTEXT_TOKENS`, `CLAUDE_CODE_AUTO_COMPACT_WINDOW`, `CLAUDE_CODE_MAX_OUTPUT_TOKENS`) and the check of their values. |
| `providers.py` | `Provider` (four ranked models, `tiers`; `models` and `aliases` come from them), `fill_tiers`, the built-in `CLAUDE`, `ProviderStore` (`providers.json`: the providers of the user and their encrypted keys; an unknown id is Claude), `new_provider_id`. |
| `agent_choices.py` | `models_for`, `with_provider`: the models offered for a provider, and what an agent becomes when its provider changes. |
| `settings.py` | `Settings`: JSON file in the user configuration folder; only invalid or unknown values are dropped; also the places of `workspaces/` and `providers.json`. |
| `jsonstore.py` | Reading and writing the JSON files: atomic write, `.bak` backup, damaged file set aside (`.corrupt`). |
| `workspace_state.py` | `WorkspaceState`: per workspace, the current conversation and the main agent of each conversation, the trust of the folder (`trusted`, `approval_asked`, `existed`) and the approved record of each watched file, `WatchRecord` (`workspaces/<hash>.json`; the copies are in `workspaces/<hash>.watch/`). |
| `workspace_stats.py` | `WorkspaceStats`: per workspace, the ledger of what all its conversations used, deleted ones included (`workspaces/<hash>.stats.json`), and the lines that show it. |
| `shortcuts.py` | Configurable commands, shortcut notation (`Ctrl+Shift+O`), rules and conflicts. |
| `workspaces.py` | Recent workspaces (missing folders are dropped) and how a workspace is listed. |

### `core/security/`: trusted folders, secrets and the key (`security.md`)

| Module | Role |
|---|---|
| `sensitive.py` | Which names look like a credential or redirect the traffic (`is_credential_name`, `redirects_traffic`), and the masking of secrets in JSON (`mask_secrets`, `mask_json_text`): a credential key is replaced by a hash, an URL keeps only its scheme, host and port. |
| `watch.py` | `WatchedFiles`: the files that can change what the CLI does, their SHA-256 and masked copy, the changes against what was approved, the differences, `approve` / `set_watched` / `forget`; also the one door for writing a settings file (`write_json`, `verify`, `ExternalChangeError`). |
| `restricted.py` | The restricted launch of a folder not approved: `--setting-sources user`, the `deny` / `ask` rules of the project as inline settings, the permission mode (`plan` and `dontAsk` kept, else `manual`). |
| `vault.py` | `KeyVault` (Protocol) and `DpapiVault`: the key of a provider encrypted with the Windows DPAPI. |
| `key_relay.py` | `KeyRelay` and `RelayAccess`: the local relay (standard `ThreadingHTTPServer`, `127.0.0.1`) that holds the key of a provider, gives the CLI a throw-away token per provider and forwards the requests with the real key, streaming the answers; starts on demand, stops after 10 minutes without a request. Held by `Shared.relay` and stopped when the window closes. |

### `core/remote/`: the remote control (`remote.md`)

| Module | Role |
|---|---|
| `protocol.py` | The five commands (`interrupt`, `send`, `last`, `announcements`, `version`), `PROTOCOL_VERSION`, the fields of `last`, the error codes, `parse_request` (a request that is not valid is refused before it reaches the application) and the JSON responses. |
| `pipe_server.py` | `PipeServer`: the named pipe `\\.\pipe\WxClaude-<user>` (`pipe_name`), one request and one response per connection, in a thread; no key, the raw bytes of the pipe. |
| `endpoint.py` | `RemoteEndpoint`: checks a request in the thread of the pipe, has it run on the interface thread (`run_in_ui` is `wx.CallAfter`) and waits for the response; a request that is late is answered `timeout` and never run; `version` is answered at once. |

### `core/speech/`: what is said (announcements, screen reader outputs, sounds)

| Module | Role |
|---|---|
| `announcements.py` | `Announce` messages, their `Category` and the `Destination` chosen per category, `AnnouncementCenter`, the message sinks and the sound players. |
| `claude/tool_target.py` | `tool_detail`: what a tool call works on (file name without folder, program of a command, pattern, host, query), for the history only: `progress_for` adds it to the values of the announcement (`target`, `history_as`) and `AnnouncementCenter` writes the detailed message (`CLAUDE_USING_TOOL_ON`, `CLAUDE_USING_TOOL_TO_RUN`) in the history while the spoken text stays `CLAUDE_USING_TOOL`. |
| `history.py` | `AnnouncementHistory`: the last 500 announcements with their time (`14:32 Claude has answered.`), in memory; a change of workspace or conversation follows a blank line. `AnnouncementCenter` fills it (every announcement but movements and searches, whatever its destination). |
| `sounds.py` | `WinsoundPlayer`: plays the two WAV files of `wxclaude/sounds` (Message.wav, Permission.wav). They are made by synthesis, so they belong to the project: `packaging/make_sounds.py <folder>` writes the candidates to listen to, `--install` writes the chosen ones (`CHOSEN`) into the package. |
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
| `shared.py` | `Shared`: what the presenters of the window work on together (settings, usage of Claude, `ClaudeFiles`, the trust state, the providers); `ConversationState`: which conversation is the current one (owned by `ConversationPresenter`, read by `ConversationLoader`); `read_session`: read a session file and show the error if it cannot be read. |
| `security_presenter.py` | `SecurityPresenter`: the trust state of the current workspace: the offer to approve a new folder, the alert about changed files, approve / restrict, `restricted`, and the `guard` through which the settings files are written. |
| `security_tab_presenter.py` | `SecurityTabPresenter`: the tab Security (trusted folder, watched files, accept a change, add / remove a file). |
| `providers_presenter.py` | `ProvidersPresenter`: the Providers page (list, add, edit, delete; every action saved at once, the key typed in the form with it). |
| `provider_form_presenter.py` | `ProviderFormPresenter` and `ProviderEdit`: the form of a provider (the key button, held until the form is accepted, and the button for the models). |
| `env_vars_presenter.py` | `EnvVarsPresenter`: the tab Environment variables (target file, variables, enable / set / remove, a warning for the versioned file). |
| `claude_check.py` | `ClaudeCheck`: is Claude Code found? (at the start and when its path changes); `ClaudeCheckView` is what it asks of the interface. |
| `login_presenter.py` | `LoginPresenter`: the sign-in to Claude Code (start with an optional e-mail address, cancel, close; the state read again at the end); `LoginView` is what it asks of the dialog. |
| `run_presenter.py` | `RunPresenter`: a message sent to Claude (start, events, permission questions, progress, steps, end, interrupt; `stop` when the window closes and `claude_path` give the window what it needs of the runner) and the reading of the gauges (`refresh_gauges_if_due`, handled like a message: busy, silent), linked to the window by `RunLinks`; `RunView` is what it asks of the interface. |
| `permission_handler.py` | `PermissionHandler`: the questions Claude asks during a message (permission to use a tool, structured questions, questions that expired, rules allowed for the message); `RunPresenter` owns it and hands the events to it. |
| `gauge_reader.py` | `GaugeReader`: the reading of the gauges with `/usage` (when they are due, silent, handled like a message) and the announcement of the gauges that reach their alert. `RunPresenter` owns it; its `busy` also covers a reading. |
| `provider_variables_editor.py` | `ProviderVariablesEditor`: the list *Variable* of the form of a provider (the four models, then the variables of the CLI it can set), the value of each line, its explanation and the provider's `tiers` and `env` it gives back. |
| `conversation_navigator.py` | `ConversationNavigator`: the jumps of the conversation (headings, tables, lists, items, links): where the caret goes and what is said on arriving or when there is nothing further. The view gives it the text, the caret, a way to move it and `say`. |
| `conversation_presenter.py` | `ConversationPresenter`: the current conversation (identifier, name, main agent) and the commands of the Conversation menu (new, resume, refresh, rename, branch, agent); whether there is a conversation (`has_conversation`) and sending the prompt (`can_send`, `send`: the text is trimmed, the agent is the conversation's or the alternative one, Claude is started through `ConversationLinks.start`, and the prompt is emptied only if it started); the title of the window (the name of a conversation is the one of its session: `--name`, `/rename`); what is remembered in the workspace file (current conversation, main agent). |
| `conversation_loader.py` | `ConversationLoader` and `LoaderLinks`: showing the conversations that Claude Code holds for the workspace (select one when a workspace is opened, resume one, read the current one again), taken out of `ConversationPresenter`, which keeps making a conversation the current one. |
| `progress_announcer.py` | `ProgressAnnouncer`, `ProgressLinks`: what is said while Claude answers (progress without repeating the same text twice, the notices at the start of the CLI, the step of the task list), taken out of `RunPresenter`. |
| `stats_recorder.py` | `StatsRecorder`: adds each finished message to the statistics of the workspace, without the time the user took to answer the permission questions. |
| `workspace_presenter.py` | `WorkspacePresenter`: the current workspace (and the opening of its trust state), what is remembered about it and its statistics (counted from the existing conversations at the first use); open a folder, a Claude project, a recent workspace, the last one at startup. The window does what follows (`WorkspaceLinks`). |
| `search_presenter.py` | `SearchPresenter`: Find, Find next and Find previous in the conversation; keeps the last search. |
| `message_presenter.py` | `MessagePresenter`: the details of a message (tools, table, links), copying it or its exchange, the task list and the plans. |
| `usage_presenter.py` | `UsagePresenter`: the dialog *Usage gauge* (gauges of Claude, then the credit of the providers that tell it, asked away from the window thread) and the dialog *Statistics* (spending, then the workspace). |
| `file_presenter.py` | `FilePresenter`: export the conversation, show the workspace folder in the file explorer, the help page, About. |
| `workspace_settings_presenter.py` | `WorkspaceSettingsPresenter`, `WorkspaceSettingsLinks` and `WorkspaceEdit`: the settings of the workspace. The files that the user approved are checked, the rules are loaded, the dialog edits them in memory, and they are written once it is validated (a file changed from outside is given to `SecurityPresenter`); the alternative agent of the workspace is kept through the links. |
| `announcements_presenter.py` | `AnnouncementsPresenter`: the destination of each category of announcements, edited in the Announcements page until OK. |
| `remote_presenter.py` | `RemotePresenter` and `RemoteLinks`: what the commands of the remote control do (interrupt, send, the last answer with its status and tokens, the announcements); no wx, no pipe (`remote.md`). |

## Modules of `ui/`

| Module | Role |
|---|---|
| `main_window.py` | The conversation view, the prompt and the buttons, the menus, and the wiring of the presenters and their views. |
| `conversation_screen.py` | `WxConversationScreen`: the view of `ConversationPresenter` (conversation view, prompt, title, name and agent dialogs, the confirmation and the Recycle Bin of a deletion). |
| `claude_check_view.py` | `WxClaudeCheckView`: the view of `ClaudeCheck` (status bar, the message that offers the Preferences). |
| `login_dialog.py` | `LoginDialog`: the sign-in dialog, the view of `LoginPresenter` (it is the view itself: `wx.CallAfter`, its own message boxes). |
| `run_view.py` | `WxRunView`: the view of `RunPresenter` (conversation view, status bar, permission dialog, `wx.CallAfter`). |
| `gauge_watch.py` | `GaugeWatch`: the one-minute timer that asks whether the gauges are to be read (started by the application, not by the window). |
| `feedback.py` | `Feedback`: the status bar (position, messages), the announcements, and every dialog of the window through `modal`, which puts the focus back (`focus.md`); also `choose` (pick in a list), `confirm` (Yes / No, No by default) and `read_session` (the error is shown). |
| `workspace_view.py` | `WxWorkspaceView`: the view of `WorkspacePresenter` (folder dialog, messages). |
| `file_view.py` | `WxFileView`: the view of `FilePresenter` (export dialog, file explorer, browser, About). |
| `conversation_view.py` | The read-only Markdown field: keys for the headings, tables, lists and items, search selection, `focus_last_prompt`, `replace_messages` (rebuild the text, the caret staying on its message), the
line that sums up the tools, the context menu of a message. |
| `preferences_dialog.py`, `preferences_pages.py` | Preferences: the notebook, OK and the validation of the pages; one class per page (General, Claude, Workspace, Agent, Announcements; Providers and Shortcuts in their own modules), each applying its own values. |
| `shortcuts_page.py` | The page to choose shortcuts, independent of the settings (commands and shortcuts are given to it); it can be copied with `core/config/shortcuts.py`, `shortcut_keys.py` and `fields.py`. |
| `fields.py` | `read_only_field`: the read-only multi-line field the Tab key reaches. |
| `menus.py` | Menus described as tables (`MenuEntry`: text, handler, configurable command, what it needs, check item); `add_entries` appends and binds them. |
| `main_menu.py` | `MainMenu`: the menu bar of the main window (tables, recent workspaces, shortcuts, greying), told what each item does by `MenuHandlers`. |
| `display_options.py` | `DisplayOptions`: what the user chooses to see of the conversation (system messages, summary of the tools, marks of bold and italic). Settings, view and check items of the menu are put together: `apply` at the start and after the Preferences, one method for each item of the menu. |
| `message_view.py` | `WxMessageView`: the view of `MessagePresenter` (dialogs of the details, tasks and plans; clipboard, browser). |
| `history_dialog.py` | `show_history`: the history of the announcements in a `TextDialog` (Help menu), the caret on the last line. |
| `usage_view.py` | `WxUsageView`: the view of `UsagePresenter` (two `TextDialog`s; the credits are asked by `worker.run_in_background`). |
| `worker.py` | `run_in_background`: work in a thread, the result comes back to the window thread with `wx.CallAfter` (nothing is called once the window is gone). |
| `search_view.py` | `WxSearchView`: the view of `SearchPresenter` (Find dialog, selection in the conversation view). |
| `desktop.py` | The clipboard, the browser, the file explorer and the Recycle Bin (`SHFileOperationW`); each function says whether the desktop refused. |
| `workspace_settings_dialog.py` | Workspace settings: the permission rules of the `.claude` files (tab Tools), the tabs below, and the tab *Alternative agent* (an `AgentPanel`). |
| `workspace_settings_view.py` | `WxWorkspaceSettingsView`: the view of `WorkspaceSettingsPresenter` (opens the dialog above, gives back what was validated, the messages). |
| `env_vars_page.py`, `security_page.py` | The tabs Environment variables and Security: the views of `EnvVarsPresenter` and `SecurityTabPresenter`. |
| `security_view.py` | `WxSecurityView`: the view of `SecurityPresenter` (the offer to approve a folder, the alert as a `ListDialog`). |
| `providers_page.py`, `provider_dialogs.py` | The Providers page of the Preferences (view of `ProvidersPresenter`: the list, the choice of the key transmission), the form of a provider (view of `ProviderFormPresenter`) and the entry of a key. |
| `agent_panel.py`, `agent_dialog.py` | The fields of an agent (provider, model, effort, permission mode), and the dialog to modify the agent of the conversation. |
| `permission_dialog.py` | The permission question of Claude. |
| `question_dialog.py` | `QuestionDialog`: the structured questions of Claude (`core/claude/questions.py`), a list of choices and a field of one's own per question. |
| `search_dialog.py` | The Find dialog (term, match case, whole words). |
| `conversation_name_dialog.py` | Name of a new, renamed or branched conversation. |
| `list_dialog.py` | `ListDialog(parent, spec, actions)`: a list of lines (from a `ListSpec`), the details of the selected one, a Close button and optional action buttons; the base of the three next dialogs. |
| `table_dialog.py` | `TableCellsDialog`: a table shown one column at a time (a list of the rows, Left/Right change the column, a field holds the cell), used by `message_view.TABLE_DIALOG`; the old `TableDialog` of `details_dialogs.py` (one sentence per row) comes back by changing that one line. |
| `tasks_dialog.py`, `plans_dialog.py`, `details_dialogs.py`, `text_dialog.py` | Task list; plans; tools used, rows of a table and links of a message; `TextDialog`, a read-only text and a Close button (the usage of Claude, the models of a provider). |
| `shortcut_keys.py` | wx key events to the shortcut notation. |
| `focus_keeper.py` | `FocusKeeper`: Alt+Tab away and back, the focus returns to the control it was on, once; a button or a control that is greyed or hidden by then gives the default control of the window (`focus.md`, rule E). |
| `prompt_area.py` | `PromptArea`: the label, the field and the three buttons of the prompt, the labels with their shortcuts and the keys that send. The controls are children of the panel of the window (the label stays right before its field); what sending does is given by the window (`PromptActions`). |
| `prompt_field.py` | `PromptField`: the prompt (a plain multi-line field) with its context menu: Cut, Copy, Paste and Modify the agent (the action and the shortcut shown are given by the window). |
| `menu_keys.py` | The keys that ask for a context menu (Applications, Shift+F10), for the conversation view and the prompt. |
| `message_sinks.py`, `uia_provider.py` | Announcements sent as UI Automation notifications (`ctypes`). |
| `wx_locale.py` | Language of wx's own texts. |
| `single_instance.py` | Only one WxClaude per user (`wx.SingleInstanceChecker`); a second launch brings the first window to the front. |
| `remote_control.py` | `RemoteControl`: the pipe of the option `--remote` tied to `wx.CallAfter`; the window builds its `RemoteLinks`, shows *Remote enabled* in its title and stops it when it closes. |

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
settings, and `env_vars.txt` the environment variables of the tab Environment variables (name, kind,
whether a project file applies it, explanation, in one language; its header says how to edit it);
they are package data. The settings files of WxClaude and of Claude Code are described in
`settings.md`.

## Translations

Message ids are English, the catalog is `locale/fr/LC_MESSAGES/wxclaude.po` (recompile with Babel,
see `CLAUDE.md`). Sentences are never concatenated: `str.format` with named fields.
