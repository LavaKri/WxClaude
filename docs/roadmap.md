# Roadmap

Start here in a new session. Read `CLAUDE.md` (rules), then this file, then the spec of the feature
you work on (`conversation-display.md`, `claude-cli.md`, `interface.md`, `settings.md`).

## Decisions taken

- **One machine only.** WxClaude runs on a single computer. No server/client split, no network, no
  JSON protocol of our own, no second executable. The runner sends typed events (dataclasses)
  straight to the interface. (If two machines are wanted one day, those events are the natural
  thing to serialize.)
- **Display**: a read-only text field holding the conversation as a Markdown document, navigation
  by headings (see `conversation-display.md`). First version: only the user's prompts and Claude's
  answers; everything else (tools, tables, links) later, in dialogs.
- **Progress**: status bar (not focusable) + UI Automation announcements + a shortcut to read it.
- **Agents** replace the word "profile": model, effort, permission mode. An alternative agent is
  used by Shift+Enter. Changing the model loses the prompt cache, the rest does not
  (`claude-cli.md`).
- **A conversation always belongs to a workspace** and has an identifier (the CLI session id,
  chosen by the application with `--session-id`). At startup the last workspace is opened and its
  conversation only selected.
- **No subagents** when working on this project (see `CLAUDE.md`).
- Nothing in the code or docs may refer to another project.

## Done

Skeleton, menus, options (General, Agent, Shortcuts, Screen reader), configurable shortcuts,
agents, conversation names, workspaces (recent, from Claude projects, last one reopened),
UI Automation announcements, task list dialog (empty), documentation. See `interface.md`.
Milestone 1 (below): `core/messages.py` (`Message`, `ToolUse`, `Usage`) and
`core/session_reader.py` (`read_session`), tested on synthetic session files.
Claude is **not launched yet**: sending a prompt only echoes it.

## Next milestones

1. ~~**Conversation model and history**~~ (done, `core/`, no wx)
   - `Message` (id, role, text, model, effort, hidden flag, details kept but not displayed:
     tools, tool results, thinking, usage).
   - Reader of the session files (`~/.claude/projects/<folder>/<id>.jsonl`): only prompts and
     answers for now, duplicates removed, noise flagged hidden, title, token usage, last model
     and permission mode (the effort is not in the files).
   - Not done yet: listing the sessions of a workspace (needed by "Resume a conversation").
2. **Display**
   - Markdown heading parser (markdown-it-py, CommonMark), UTF-16 position conversion,
     navigation (T, Shift+T, 1 to 6, Shift+digit), announcement "title text, title N".
   - `ConversationView` in the main window; message spans for context menus and copy.
   - Enable "Resume a conversation" (list of the sessions of the workspace).
3. **Runner**
   - `claude -p --output-format stream-json` from the agent (`--model`, `--effort`,
     `--permission-mode`), `--session-id` for the first message, `--resume` afterwards.
   - Reader threads for stdout and stderr, events to the interface with `wx.CallAfter`.
   - A fake `claude` for the tests. Interrupt. Busy state (Send greyed, Interrupt active).
   - Progress in the status bar and announced. After each turn, re-read the session file to
     catch anything missed.
4. **Permissions**: the question dialog, "always allow" rules, deny and explain.
5. **Details dialogs** (context menu in a message body): tools used, tables, links. **Claude
   usage** dialog (Tools menu). Task list filled from `~/.claude/tasks/<id>/*.json`.
6. **Rename, branch (`--fork-session`), delete**, export.
7. **Packaging** (PyInstaller) and manual checks with NVDA and JAWS.

## Open questions

- Where is the name of a conversation kept: in settings (now) or written in the session file
  (a `custom-title` line, so Claude Code shows it too)?
- Errors from Claude: status bar plus a dialog, outside the conversation text? (proposed)
- Default shortcuts to read the progress and to open the Claude usage dialog.
- Do UI Automation notifications reach JAWS (they reach NVDA and Narrator)? Test, with a
  focusable progress field as fallback.
- Reading the usage gauge without sending a message (not found yet).
- Shall "At startup" also be able to reopen without selecting the conversation?
