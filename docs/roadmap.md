# Roadmap

Start here in a new session. Read `CLAUDE.md` (rules), then this file, then the spec of the feature
you work on (`conversation-display.md`, `claude-cli.md`, `interface.md`, `settings.md`).
What is still to decide, to verify or to improve is in `open-questions.md`.

## Decisions taken

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
  process.
- **One instance** of WxClaude per user; a second launch brings the first window to the front.
- **Names of conversations** are kept by WxClaude only; the session files of the CLI are never
  written by WxClaude.
- **Errors from Claude** (CLI not found or not logged in, process failure, API error such as an
  overload or a reached limit, result with an error) go to the status bar and to a dialog, never
  into the conversation text.
- **Titles**: prompts are level 1, answers level 2 (`conversation-display.md`); the wording is kept.
- **Usage dialog**: `Ctrl+Shift+U`.
- **No migration** of older settings files: only the keys described in `settings.md` are read.
- **No subagents** when working on this project (see `CLAUDE.md`).
- Nothing in the code or docs may refer to another project.

## Done

Skeleton, menus, options (General, Conversation, Agent, Shortcuts, Screen reader), configurable shortcuts,
agents, conversation names, workspaces (recent, from Claude projects, last one reopened),
UI Automation announcements, task list dialog (empty), documentation. See `interface.md`.
Milestone 1 (below): `core/messages.py` (`Message`, `ToolUse`, `Usage`) and
`core/session_reader.py` (`read_session`), tested on synthetic session files.
Milestone 3 (below), except the permission questions: Claude is launched, the answer is shown
and the session file is read again after each turn.

## Next milestones

1. ~~**Conversation model and history**~~ (done, `core/`, no wx)
   - `Message` (id, role, text, model, effort, hidden flag, details kept but not displayed:
     tools, tool results, thinking, usage).
   - Reader of the session files (`~/.claude/projects/<folder>/<id>.jsonl`): only prompts and
     answers for now, duplicates removed, noise flagged hidden, title, token usage, last model
     and permission mode; the effort of each answer is the `effort` field of its entry.
2. ~~**Display**~~ (done, to check by hand with NVDA and JAWS)
   - Markdown heading parser (markdown-it-py, CommonMark), UTF-16 position conversion,
     navigation (T, Shift+T, 1 to 6, Shift+digit), announcement "title text, title N".
   - `ConversationView` in the main window; message spans for context menus and copy.
   - "Resume a conversation" (`list_sessions` in `core/claude_projects.py`, sorted by last
     message, choice dialog, the history is loaded in the view). Opening a workspace selects its
     remembered conversation, else the most recent, else none. A file per workspace remembers
     the main agent and the name of each conversation (`settings.md`). Refresh the conversation
     (F5). The option "Hide the system messages" shows or hides the noise of the session. Search
     in the conversation (Ctrl+F, F3, Shift+F3; `interface.md`).
3. ~~**Runner**~~ (done, to check by hand with NVDA and JAWS)
   - `claude -p --output-format stream-json --verbose` from the agent (`--model`, `--effort`,
     `--permission-mode`), the prompt through stdin, `--session-id` for the first message,
     `--resume` afterwards (`core/runner.py`, `core/stream.py`, `core/events.py`).
   - Reader threads for stdout and stderr, events to the interface with `wx.CallAfter`.
   - A fake `claude` for the tests (`tests/fakes/fake_claude.py`). Interrupt. Busy state (Send
     greyed, Interrupt active).
   - Progress in the status bar and announced (option). After each turn, the session file is read
     again and the view is rebuilt if it differs.
   - A tool that needs permission is denied by the CLI (`-p` has nobody to ask): the denial is shown
     as progress. The question dialog is milestone 4.
4. **Permissions**: the question dialog, "always allow" rules, deny and explain.
5. **Details dialogs** (context menu in a message body): tools used, tables, links. **Claude
   usage** dialog (Tools menu). Task list filled from `~/.claude/tasks/<id>/*.json`.
6. **Rename, branch (`--fork-session`), delete**, export.
7. **Packaging** (PyInstaller) and manual checks with NVDA and JAWS.
