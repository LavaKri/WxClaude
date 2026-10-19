# Architecture

WxClaude is a wxPython desktop front end for `claude -p --output-format stream-json`.

- `core/`: logic, never imports `wx` (mypy strict).
- `ui/`: thin wx layer.
- Worker threads (CLI reader, permission hook server) never touch wx; they post to the UI with
  `wx.CallAfter`.

## Scope

WxClaude runs on **one machine**: there is no server/client split, no network and no protocol of
our own. The runner will send typed events (dataclasses) straight to the interface, through
`wx.CallAfter`. The CLI's session file stays the reference for what was said.

## Current state

Only the interface exists. Claude is not launched yet: sending a prompt echoes it in the
conversation view. The plan, in order, is in `roadmap.md`: conversation model and history, the
display (`conversation-display.md`), then the runner, tested first with a fake `claude`. What is
known about the CLI is in `claude-cli.md`.

## Modules of `core/`

| Module | Role |
|---|---|
| `agents.py` | `Agent`: model, effort and permission mode (each optional); `over()` layers one on another. Models are listed by ascending power. |
| `settings.py` | `Settings`: JSON file in the user configuration folder; only invalid or unknown values are dropped. |
| `shortcuts.py` | Configurable commands, shortcut notation (`Ctrl+Shift+O`), rules and conflicts. |
| `workspaces.py` | Recent workspaces (missing folders are dropped) and how a workspace is listed. |
| `claude_projects.py` | The folders Claude Code has worked in, read from `<config>/projects`. |
| `conversations.py` | Conversation identifiers (UUID, the session id of the CLI) and proposed names. |
| `announcements.py` | `Announce` messages, `AnnouncementCenter` and the message sinks. |
| `screen_reader.py` | The outputs available for announcements (none, UI Automation). |
| `export.py` | Writes the conversation text to a file. |
| `errors.py` | `WxClaudeError` and its subclasses. |

## Modules of `ui/`

| Module | Role |
|---|---|
| `main_window.py` | Menus, conversation view, prompt, buttons; enables what needs a workspace or a conversation. |
| `options_dialog.py` | Options, one tab per topic. |
| `agent_panel.py`, `agent_dialog.py` | The fields of an agent, and the dialog to modify the agent of the conversation. |
| `conversation_name_dialog.py` | Name of a new, renamed or branched conversation. |
| `tasks_dialog.py` | Task list of the conversation (empty for now). |
| `shortcut_keys.py` | wx key events to the shortcut notation. |
| `message_sinks.py`, `uia_provider.py` | Announcements sent as UI Automation notifications (`ctypes`). |
| `wx_locale.py` | Language of wx's own texts. |

## Workspaces and conversations

A conversation always belongs to a workspace (the working folder of the CLI). Without a workspace
there is no conversation; opening another workspace closes the current conversation. The
identifier of the current conversation and of the last workspace are saved, and at startup (option
"At startup, open the last workspace") the workspace is opened and that conversation is only
selected, nothing is loaded.

## Translations

Message ids are English, the catalog is `locale/fr/LC_MESSAGES/wxclaude.po` (recompile with Babel,
see `CLAUDE.md`). Sentences are never concatenated: `str.format` with named fields.
