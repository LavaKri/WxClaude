# Settings file

`settings.json` in the user configuration folder (`platformdirs`, application `WxClaude`). Missing or
invalid values fall back to their default; unknown keys are ignored.

| Key | Meaning | Default |
|---|---|---|
| `language` | `fr` or `en` | `fr` |
| `default_agent` | Agent of a new conversation (`model`, `effort`, `permission_mode`) | `sonnet`, `medium`, `manual` |
| `alternative_agent` | Agent for "send with the alternative agent" | effort `low` |
| `recent_workspaces` | Recent workspaces, most recent first (ten at most) | empty |
| `shortcuts` | Only the shortcuts that differ from the default, by command id; `""` is no shortcut | empty |
| `screen_reader_output` | `none` or `uia` | `uia` on Windows |
| `reopen_last` | At startup, open the last workspace | `true` |
| `last_workspace` | Folder to reopen | empty |
| `last_conversation_id` | Identifier (UUID) of the conversation to select | empty |
| `last_conversation_name` | Its name | empty |
| `conversation_counter` | Number proposed in `Conversation x` | `1` |

Valid values: `effort` is one of `low`, `medium`, `high`, `xhigh`, `max`; `permission_mode` is one of
`manual`, `acceptEdits`, `plan`, `auto`, `dontAsk` (`bypassPermissions` is deliberately not offered).

## Shortcut commands

`workspace.open` (Ctrl+O), `conversation.new` (Ctrl+N), `conversation.resume` (Ctrl+Shift+O),
`claude.interrupt` (Ctrl+Shift+I), `tasks.list` (Ctrl+T), `prompt.send` (Ctrl+Enter),
`prompt.send_alternative` (Shift+Enter).
