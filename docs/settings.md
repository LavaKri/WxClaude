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
| `claude_auto_search` | Look for `claude` in the PATH | `true` |
| `claude_path` | The `claude` executable chosen by hand, used when the automatic search is off | empty |
| `permission_channel` | How Claude's permission questions reach WxClaude: `stdio` (control protocol) or `hook` (HTTP hook); see `claude-cli.md` | `stdio` |
| `hook_timeout_minutes` | With the `hook` channel, how long the CLI waits for the answer (1 to 10) | `10` |
| `last_workspace` | Folder to reopen | empty |
| `hide_system_messages` | Do not display the noise the CLI writes in a session | `true` |
| `announcements` | Only the destinations that differ from the default, by category id (`progress`, `step`, `end_of_answer`, `permission_question`, `permission_answer`, `headings`, `no_more_heading`, `search`, `search_failed`, `refresh`, `gauge`): `none`, `message`, `read_line`, `dialog`, `sound_1`, `sound_2`. A destination the category does not accept, or an unknown one, is ignored | empty |
| `local_tools_only` | The workspace settings only modify the personal file `.claude/settings.local.json`, never the versioned `settings.json` | `false` |
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
    "<uuid>": {"agent": {"model": "opus", "effort": "high", "permission_mode": "plan"}}
  }
}
```

The agent is the main agent of the conversation, never the alternative one. The name of a
conversation is not kept here: it is the name of its session, kept by the CLI (`interface.md`,
"Names of conversations"); a `name` found in an older file is ignored. The path is checked when
reading: a file that belongs to another path is ignored and the user is told. When a workspace is
opened, the conversations whose session file no longer exists are dropped.

`workspaces/<hash>.stats.json`, beside it, is the ledger of the statistics of the workspace (the
usage dialog shows it). It is a separate file so that nothing but the statistics is lost with it.
It holds the day of the first message counted, the number of messages, the identifier of every
conversation that had one (a deleted conversation stays), the tokens (input, output, written to the
cache, read from the cache), the time of work in milliseconds, the cost in dollars at list price and,
for each model, its messages and its cost. Each finished message is added to it. The first time a
workspace is opened (no such file), the conversations that exist are counted once from their session
files and `includes_past` is set; there is no way to reset it.

## Settings files of Claude Code

The permission rules (allow / ask / deny) are not kept by WxClaude but in the settings files of
Claude Code, so the CLI uses them too:

| Name in the dialog | File | Written by WxClaude | Shared |
|---|---|---|---|
| general | `~/.claude/settings.json` (or `$CLAUDE_CONFIG_DIR\settings.json`) | never | no, all projects of the user |
| Settings | `<workspace>\.claude\settings.json` | yes, unless the preference limits to the local file | yes, versioned |
| SettingsLocal | `<workspace>\.claude\settings.local.json` | yes | no, personal |

The lists `permissions.allow`, `permissions.ask` and `permissions.deny` are merged across the files and
the CLI applies deny, then ask, then allow, whatever the file. When a file is written, the other keys
are kept; it is written atomically without a backup file, and a file that is not valid JSON, or whose
`permissions` is not an object, is never overwritten. The CLI reloads these files while it runs.

## Robustness of the files

The principles (atomic write, backup, a file that cannot be read is set aside) are in
`working-rules.md`, section "Files and data". Here is how WxClaude applies them.

`settings.json` and the files of the workspaces are written to a temporary file of the same folder
and then moved over the old one (a crash never leaves a half-written file). The last valid version is
kept as `<name>.bak`, and a file that cannot be read is renamed `<name>.corrupt`, so nothing is lost.
At reading, a damaged file gives its backup, else the default values, and the user gets a warning
dialog instead of a crash. Only one instance of the application runs per user (a second launch
brings the first window to the front and quits), so two instances never write the same files.
The running instance publishes the handle of its window in `instance.json`, next to
`settings.json` (`{"pid": ..., "handle": ...}`); a second launch uses it only if the handle is
still a window of that process.

Valid values: `effort` is one of `low`, `medium`, `high`, `xhigh`, `max`; `permission_mode` is one of
`manual`, `acceptEdits`, `plan`, `auto`, `dontAsk` (`bypassPermissions` is deliberately not offered).

## Shortcut commands

`workspace.open` (Ctrl+O), `conversation.new` (Ctrl+N),
`conversation.resume` (Ctrl+Shift+O), `conversation.refresh` (F5), `search.find` (Ctrl+F),
`search.next` (F3), `search.previous` (Shift+F3),
`claude.interrupt` (Ctrl+Shift+I), `tasks.list` (Ctrl+T), `claude.usage` (Ctrl+Shift+U),
`prompt.send` (Ctrl+Enter), `prompt.send_alternative` (Shift+Enter).
