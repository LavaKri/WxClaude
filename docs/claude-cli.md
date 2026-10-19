# What we know about the Claude Code CLI

Facts gathered while designing WxClaude (CLI 2.1.286 at the time). Check again if the version
changes a lot. Items marked *(to verify)* were not tested.

## Running it

- Non-interactive: `claude -p "<prompt>" --output-format stream-json --verbose` (the tests used
  `--verbose`). One process per message; the conversation continues with `--resume <id>`.
- The application chooses the conversation id: `--session-id <uuid>` for the first message
  (tested), `--resume <uuid>` afterwards. `--fork-session` with `--resume` creates a new id.
- Per message: `--model` (aliases `haiku`, `sonnet`, `opus`, `fable`, or a full name), `--effort`
  (`low`, `medium`, `high`, `xhigh`, `max`), `--permission-mode` (`manual`, `acceptEdits`,
  `plan`, `auto`, `dontAsk`, `bypassPermissions`), `--allowedTools` (rules the CLI may use without
  asking, e.g. `Bash(git *)`), `--tools` (the tools that exist at all).
- `--include-partial-messages` gives partial text; without it every block arrives complete (this is
  what the display relies on). `--input-format stream-json` allows several messages on one
  process *(to verify)*. `--no-session-persistence` would prevent resuming.
- The CLI uses the login of the user who runs it: run WxClaude in the user's own session.
- The permission mode `auto` and `bypassPermissions` do not take effect from project settings,
  only from user settings or the command line. In recent versions `auto` is the starting mode of
  interactive sessions: "not set" may mean `auto` *(to verify with `-p`)*.

## Permission modes (from the documentation)

| Mode | Runs without asking |
|---|---|
| `manual` (`default` in settings) | reads only |
| `acceptEdits` | reads, file edits, common file commands (`mkdir`, `touch`, `mv`, `cp`, ...) |
| `plan` | reads, plus commands approved by the classifier when auto mode is available |
| `auto` | everything, with background safety checks by a classifier |
| `dontAsk` | reads in the working folders and pre-approved tools; anything else is denied |
| `bypassPermissions` | everything (not offered by WxClaude) |

## Prompt cache (measured)

Same conversation, resumed, `usage.cache_read_input_tokens` after each change:

- effort changed (low, high, low, with sonnet): cache fully read again, 65 tokens created;
- permission mode changed: cache read again;
- **model changed (haiku to sonnet): 0 tokens read, everything created again** (about 4 times the
  cost, partly because of the model price).

So an alternative agent may change the effort and the permission mode freely; changing the model
costs the cache of the conversation. (Haiku seems to ignore the effort.)

## The stream (`stream-json`)

One JSON object per line:

- `system` / `init`: `session_id`, `model`, `permissionMode`. `system` / `thinking_tokens`
  (`estimated_tokens`). `system` / `permission_denied` (`tool_name`, `tool_use_id`, `message`,
  `decision_reason_type`).
- `assistant`: `message.content[]` with **one block per message** (`thinking`, `tool_use` or
  `text`), `message.model`.
- `user`: carries the `tool_result` blocks (`tool_use_id`, `is_error`, `content`).
- `rate_limit_event`: `rate_limit_info` (`status`, `rateLimitType`, `utilization`, `resetsAt`,
  `surpassedThreshold`, `isUsingOverage`, windows such as the 5-hour and the weekly gauge).
- `result`: `result` (final text), `subtype`, `usage` (`input_tokens`, `output_tokens`,
  `cache_creation_input_tokens`, `cache_read_input_tokens`), `duration_ms`, `total_cost_usd`,
  `num_turns`, `permission_denials`.
- `prompt_suggestion`: a predicted next prompt, after `result`.
- The effort is **not** reported: use the one that was requested.
- Read stdout and stderr continuously (a full pipe blocks the CLI), lines can be very long, and
  read until the end of the process before saying the turn is over.

## Session files

`~/.claude/projects/<folder>/<session-id>.jsonl` (`CLAUDE_CONFIG_DIR` is honoured). The folder
name is an encoding of the working folder that cannot always be decoded: read the `cwd` field of
the entries instead. One JSON object per line; interesting entries have `type` `user` or
`assistant` and a `message`, a `sessionId`, a `cwd`, a `timestamp`.

- Identical consecutive assistant entries exist: remove duplicates.
- Noise to hide: the answer "No response requested." and the prompt "continue".
- Messages whose model is `<synthetic>` can carry real information (for example the message that
  a usage limit was reached); keep them, they have no model and no effort.
- A user entry holding only a `tool_result` has no text of its own.
- The title is written to the file by the CLI, asynchronously (an `ai-title` entry with `aiTitle`
  *(to verify)*); a rename adds a `custom-title` entry with `customTitle` (verified, repeated many
  times in a long session: the last one wins, and it takes precedence over `aiTitle`).
- Other entry types seen, ignored by `core/session_reader.py`: `attachment`, `queue-operation`,
  `last-prompt`, `mode`, `cost-state`, `atis-latch`. Entries with `isMeta` or `isSidechain` are
  not part of the conversation. The `permissionMode` field is on user entries.
- The reader (`read_session`) skips lines that are not valid JSON (the CLI may be writing one).
- Tasks of a session: `~/.claude/tasks/<session-id>/*.json` with `id`, `subject`, `description`,
  `status` (`pending`, `in_progress`, `completed`), `blockedBy`.

## Subscription use

Driving `claude -p` from a custom front end with a subscription login may be restricted by the
usage policy of the provider; an API key is the safe path. Check the current terms.
