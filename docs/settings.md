# Settings file

`settings.json` in the user configuration folder (`platformdirs`, application `WxClaude`). Missing or
invalid values fall back to their default; unknown keys are ignored.

| Key | Meaning | Default |
|---|---|---|
| `language` | `fr` or `en` | `fr` |
| `default_agent` | Agent of a new conversation: always complete (`model`, `effort`, `permission_mode`); a missing field is taken from the default | `sonnet`, `medium`, `manual` |
| `alternative_agent` | Agent for "send with the alternative agent"; a field left out comes from the agent of the conversation | effort `low` |
| `recent_workspaces` | Recent workspaces, most recent first (ten at most) | empty |
| `shortcuts` | Only the shortcuts that differ from the default, by command id; `""` is no shortcut | empty |
| `screen_reader_output` | `none` or `uia` | `uia` on Windows |
| `reopen_last` | At startup, open the last workspace | `true` |
| `last_workspace` | Folder to reopen | empty |
| `hide_system_messages` | Do not display the noise the CLI writes in a session | `true` |
| `announce_progress` | Announce the progress of Claude while it answers | `true` |
| `conversation_counter` | Number proposed in `Conversation x` | `1` |

What is remembered about conversations is not in this file but in the file of each workspace
(below).

## Files of the workspaces

`workspaces/<hash>.json`, next to `settings.json`. The name is a 64-bit BLAKE2b hash of the lower-case
path of the workspace (16 hexadecimal characters). The file holds:

```json
{
  "workspace": "C:\\Users\\Example\\Dev\\WxClaude",
  "current_conversation": "<uuid>",
  "conversations": {
    "<uuid>": {"name": "Notes", "agent": {"model": "opus", "effort": "high", "permission_mode": "plan"}}
  }
}
```

The agent is the main agent of the conversation, never the alternative one. The name is only
kept by WxClaude: it is never written in the session files of the CLI, and it wins over the title
found in the session file. The path is checked when
reading: a file that belongs to another path is ignored and the user is told. When a workspace is
opened, the conversations whose session file no longer exists are dropped.

## Robustness of the files

`settings.json` and the files of the workspaces are written to a temporary file of the same folder
and then moved over the old one (a crash never leaves a half-written file). The last valid version is
kept as `<name>.bak`, and a file that cannot be read is renamed `<name>.corrupt`, so nothing is lost.
At reading, a damaged file gives its backup, else the default values, and the user gets a warning
dialog instead of a crash. Only one instance of the application runs per user (a second launch
shows a message and quits), so two instances never write the same files.

Valid values: `effort` is one of `low`, `medium`, `high`, `xhigh`, `max`; `permission_mode` is one of
`manual`, `acceptEdits`, `plan`, `auto`, `dontAsk` (`bypassPermissions` is deliberately not offered).

## Shortcut commands

`workspace.open` (Ctrl+O), `conversation.new` (Ctrl+N),
`conversation.resume` (Ctrl+Shift+O), `conversation.refresh` (F5),
`claude.interrupt` (Ctrl+Shift+I), `tasks.list` (Ctrl+T), `prompt.send` (Ctrl+Enter),
`prompt.send_alternative` (Shift+Enter).
