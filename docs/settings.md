# Settings file

`settings.json` in the user configuration folder (`platformdirs`, application `WxClaude`). Missing or
invalid values fall back to their default; unknown keys are ignored.

| Key | Meaning | Default |
|---|---|---|
| `language` | `fr` or `en` | `fr` |
| `default_agent` | Agent of a new conversation: always complete (`provider`, `model`, `effort`, `permission_mode`); a missing field is taken from the default | `claude`, `sonnet`, `medium`, `manual` |
| `alternative_agent` | Agent for "send with the alternative agent"; a field left out (the provider too) means "same as the conversation". It is only the first value of the alternative agent of a workspace, which then lives in `workspaces/<hash>.json` | effort `low` |
| `recent_workspaces` | Recent workspaces, most recent first (ten at most) | empty |
| `shortcuts` | Only the shortcuts that differ from the default, by command id; `""` is no shortcut | empty |
| `screen_reader_output` | `none` or `uia` | `uia` on Windows |
| `reopen_last` | At startup, open the last workspace | `true` |
| `maximize_at_start` | The main window starts maximized | `true` |
| `claude_auto_search` | Look for `claude` in the PATH | `true` |
| `claude_path` | The `claude` executable chosen by hand, used when the automatic search is off | empty |
| `permission_channel` | How Claude's permission questions reach WxClaude: `stdio` (control protocol) or `hook` (HTTP hook); see `claude-cli.md` | `stdio` |
| `refuse_plan_mode_exit` | The requests of Claude that would take the user out of the mode Plan are refused with no dialog: its plan (the request to leave the mode) and, while the agent of the message is in the mode Plan, its structured questions. Claude is told to present the plan and ask its questions in its answer; the user leaves the mode by changing the agent. Only the `stdio` channel has these requests | `true` |
| `hook_timeout_minutes` | With the `hook` channel, how long the CLI waits for the answer (1 to 10) | `10` |
| `last_workspace` | Folder to reopen | empty |
| `hide_system_messages` | Do not display the noise the CLI writes in a session | `true` |
| `show_tools_summary` | A line under each answer that used tools sums them up (item of the Display submenu) | `true` |
| `remove_markdown_marks` | The marks of bold and italic (`**`, `*`) are removed from the text of the conversation (item of the Display submenu) | `true` |
| `announcements` | Only the destinations that differ from the default, by category id (`progress`, `step`, `end_of_answer`, `permission_question`, `permission_answer`, `movement`, `movement_blocked`, `search`, `search_failed`, `refresh`, `gauge`, `security`, `mode_not_applied`, `mcp_servers`): `none`, `message`, `read_line`, `dialog`, `sound_1`, `sound_2`. A destination the category does not accept, or an unknown one, is ignored | empty |
| `local_tools_only` | The workspace settings only modify the personal file `.claude/settings.local.json`, never the versioned `settings.json` | `false` |
| `relay_idle_minutes` | The relay of the key (transmission *Relayed*) stops after that many minutes without a request, 1 to 120. No interface: set in the file, read when WxClaude starts | `10` |
| `relay_timeout_seconds` | How long the relay waits for the provider, 30 to 3600. No interface: set in the file, read when WxClaude starts | `600` |
| `key_transmission` | How the key of a provider other than Claude reaches the CLI, choice *API key transmission* of the page Providers: `masked` (the tools of Claude do not see it, the CLI forces the manual permission mode), `shared` or `relayed` (a local relay holds the key). A file from before it has the yes or no `scrub_credentials`, read as `masked` or `shared` | `masked` |
| `conversation_counter` | Number proposed in `Conversation x` | `1` |

What is remembered about conversations is not in this file but in the file of each workspace
(below).

The `provider` of an agent is the id of a provider (`providers.md`); an id that no longer exists is
read as `claude` when the agent is used. An agent of an older file, without a provider, is `claude`.

## Providers

`providers.json`, next to `settings.json`, written like the other files (atomic, `.bak`, a damaged file
set aside). Keys are never in `settings.json`.

```json
{
  "providers": [
    {
      "id": "deepseek",
      "name": "DeepSeek",
      "base_url": "https://api.deepseek.com/anthropic",
      "key_source": "stored",
      "tiers": ["deepseek-chat", "deepseek-chat", "deepseek-reasoner", "deepseek-reasoner"],
      "send_effort": true,
      "models_method": "v1",
      "credit_method": "deepseek",
      "env": {"API_TIMEOUT_MS": "600000"},
      "key": "<the key encrypted with the Windows DPAPI, in base64>"
    }
  ]
}
```

When the file does not exist (the first start) the user starts with two providers, `DeepSeek` (its key to
add; models `deepseek-v4-flash` and `deepseek-v4-pro`, gauge `deepseek`) and `Ollama`
(`http://localhost:11434`, no key, model `qwen3:4b`): `DEFAULT_PROVIDERS` in `core/config/providers.py`.
They are not written until the user changes something. Once the file exists it is all there is, so a
provider that was deleted does not come back, and an empty list stays empty; a damaged file with no
backup gives only Claude, not the defaults.

Claude is built in and never written. `key_source` is `stored` (the key above) or `none` (a local
server; a placeholder is given to the CLI); an unknown value reads as `stored`. `tiers` holds the four models
(small, medium, large, largest, none empty); a file written before them (a list `models`) gives its first
four models. `models_method` (`none`, `v1`) and `credit_method` (`none`, `deepseek`) say how to ask the
server for its models and its credit (`providers.md`); a file written before them, or an unknown
value, gives `v1` and `none`. `env` holds the variables of the CLI the provider sets, from the closed list `API_TIMEOUT_MS`,
`CLAUDE_CODE_MAX_CONTEXT_TOKENS`, `CLAUDE_CODE_AUTO_COMPACT_WINDOW` and `CLAUDE_CODE_MAX_OUTPUT_TOKENS`
(`providers.md`); a file written before it, a name outside the list
or a value that is not a text gives none. An entry without an id or a name, a second one with the same id and one
named `claude` are left out. A `key` that cannot be decrypted (another account, another computer) stays
in the file so that the user can replace or remove it.

## Files of the workspaces

`workspaces/<hash>.json`, next to `settings.json`. The name is a 64-bit BLAKE2b hash of the lower-case
path of the workspace (16 hexadecimal characters). The file holds:

```json
{
  "workspace": "C:\\Users\\Example\\Dev\\WxClaude",
  "current_conversation": "<uuid>",
  "max_turns": 0,
  "alternative_agent": {"provider": "deepseek", "model": "deepseek-chat", "effort": "low", "permission_mode": "manual"},
  "conversations": {
    "<uuid>": {"agent": {"provider": "claude", "model": "opus", "effort": "high", "permission_mode": "plan"}}
  },
  "trusted": false,
  "approval_asked": true,
  "watch": {
    ".claude/settings.json": {"watched": true, "sha256": "<hash of the approved content, empty if the file did not exist>"}
  }
}
```

`trusted` says that the user approved the folder (`security.md`); `approval_asked`, that the offer to
approve it was answered; `max_turns`, the limit of turns of a message (0 or absent: none). `watch` holds, for each file that can change what the CLI does, whether it is
watched and the SHA-256 of the content approved; the copy of that content, with its secrets hidden, is
in `workspaces/<hash>.watch/<hash of the path>-<name>.bak`. No `watch` entry means that nothing was
approved yet. `alternative_agent` is the alternative agent of the workspace, used for all its
conversations and changed only in the tab *Alternative agent* of the Workspace settings. When a
workspace is opened and the field lacks (a new workspace, or a file of an older version), each missing
field is taken from the `alternative_agent` of `settings.json`, and where that one leaves it out ("same as
the conversation") from the default agent; the value is written at the next save of the file (opening a
workspace writes nothing, so that the file keeps meaning "used before"). The agent of a
conversation is its main agent, never the alternative one. The name of a
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

The key `env` of the same files is edited by the tab Environment variables (`interface.md`), with the
explanations of `src/wxclaude/data/env_vars.txt`. Both keys are written through one door that refuses to
write over a file changed from outside since the folder was approved (`security.md`).

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
`workspace.settings` (Alt+Enter), `claude.agent` (Ctrl+Shift+A), `prompt.send` (Ctrl+Enter), `prompt.send_alternative` (Shift+Enter).
