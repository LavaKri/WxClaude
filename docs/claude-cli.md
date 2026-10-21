# What we know about the Claude Code CLI

Facts gathered while designing WxClaude (CLI 2.1.286 at the time). Check again if the version
changes a lot. Only what was tested or read in the documentation is stated here.

## Running it

- Non-interactive: `claude -p --input-format stream-json --output-format stream-json --verbose
  --permission-prompt-tool stdio`. The prompt is one JSON line on stdin
  (`{"type": "user", "message": {"role": "user", "content": "..."}}`), so there is no length limit
  of a command line (verified; `--verbose` is required with `stream-json`). stdin stays open while
  Claude works, to answer its permission questions; the process ends when stdin is closed after the
  `result` line. One process per message (WxClaude does not keep a process open); the conversation continues with
  `--resume <id>`.
- The application chooses the conversation id: `--session-id <uuid>` for the first message
  (verified: the session gets that id), `--resume <uuid>` afterwards. `--fork-session` with `--resume` creates a new id.
- Per message: `--model` (aliases `haiku`, `sonnet`, `opus`, `fable`, or a full name), `--effort`
  (`low`, `medium`, `high`, `xhigh`, `max`), `--permission-mode` (`manual`, `acceptEdits`,
  `plan`, `auto`, `dontAsk`, `bypassPermissions`), `--allowedTools` (rules the CLI may use without
  asking, e.g. `Bash(git *)`), `--tools` (the tools that exist at all).
- `--include-partial-messages` gives partial text; without it every block arrives complete (this is
  what the display relies on). `--no-session-persistence` would prevent resuming.
- The CLI uses the login of the user who runs it: run WxClaude in the user's own session.
- The permission mode `auto` and `bypassPermissions` do not take effect from project settings,
  only from user settings or the command line.

## Permission modes (from the documentation)

| Mode | Runs without asking |
|---|---|
| `manual` (`default` in settings) | reads only |
| `acceptEdits` | reads, file edits, common file commands (`mkdir`, `touch`, `mv`, `cp`, ...) |
| `plan` | reads, plus commands approved by the classifier when auto mode is available |
| `auto` | everything, with background safety checks by a classifier |
| `dontAsk` | reads in the working folders and pre-approved tools; anything else is denied |
| `bypassPermissions` | everything (not offered by WxClaude) |

## Permission questions (verified)

With `--permission-prompt-tool stdio` (and `--input-format stream-json`) the CLI asks the host before
it runs a tool that the permission mode does not allow. Without it, `-p` denies the tool at once
(a `permission_denied` system line and a failed tool result); `--permission-prompts none` does the
same on purpose.

- The question is a line on stdout: `{"type": "control_request", "request_id", "request": {"subtype":
  "can_use_tool", "tool_name", "input", "description", "tool_use_id", "blocked_path",
  "permission_suggestions": [...]}}`. The suggestions are rules to add (`{"type": "addRules",
  "rules": [{"toolName": "Bash", "ruleContent": "touch x"}], "behavior": "allow", "destination":
  "localSettings"}`), directories, and a permission mode.
- The answer is a line on stdin: `{"type": "control_response", "response": {"subtype": "success",
  "request_id", "response": {...}}}` where the inner response is `{"behavior": "allow",
  "updatedInput": <the input>}` or `{"behavior": "deny", "message": "<text>"}`. Claude is told the
  text as the result of the tool, so a denial can explain itself.
- The suggested rule has `destination: localSettings`: in the CLI it is saved in
  `.claude/settings.local.json`. In `-p` the host has to do it: WxClaude writes the *allow* rule there
  (`permissions.allow`), and the CLI then does not ask any more, in this message or the next ones.
- Verified in a real run, with a rule in `.claude/settings.local.json`: `allow` runs the tool without
  a question, `deny` refuses it without a question (`permission_denied`), `ask` asks (even when an
  allow rule also matches). Rules are merged across the settings files, deny first, then ask, then
  allow; a bare `deny` rule on a tool removes the tool from Claude's context.
- On Windows the personal file stays in the `.claude` folder of the workspace (the CLI only moves it
  to the root of a git repository on other systems).
- Some commands do not need an answer at all (`echo` runs under `manual`).

## Settings files and permission rules (from the documentation)

- Rules are written `Tool` or `Tool(specifier)`; `Tool(*)` is the same as `Tool`. As a *deny* rule,
  both remove the tool from Claude's context. The names of the tools are the exact strings of the
  documentation (`Bash`, `PowerShell`, `Edit`, `WebFetch`...).
- The lists `permissions.allow`, `permissions.ask` and `permissions.deny` of the user file
  (`~/.claude/settings.json`, or `$CLAUDE_CONFIG_DIR\settings.json`), of `.claude/settings.json`
  (shared, versioned) and of `.claude/settings.local.json` (personal) are merged. Evaluation order:
  deny, then ask, then allow; the first match wins and an allow rule cannot make an exception to a
  deny or an ask rule.
- For other keys the precedence is: managed settings, command line (`--settings`), local, shared
  project, user. `env` is an ordinary key of these files (`"env": {"NAME": "value"}`); the variables
  of the CLI are set there or in the environment of the process, never in Windows itself.
- Claude Code reloads its settings files while it runs. A committed `.claude/settings.json` has its
  `allow` rules and most `env` values wait until the folder is trusted; `deny` and `ask` rules apply
  at once. Claude Code writes `.claude/settings.local.json` itself and keeps it out of git.
- On Windows with Git Bash, a deny rule on `Bash` (even with a specifier) also turns the PowerShell
  tool off, unless `CLAUDE_CODE_USE_POWERSHELL_TOOL=1` is set or a `PowerShell(...)` rule exists.
  `CLAUDE_CODE_USE_POWERSHELL_TOOL=0` turns the tool off on Windows.
- In a `-p` run a settings file that is not valid JSON is skipped without any dialog.

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
- `rate_limit_event` (verified, one per message): `rate_limit_info` with `status` (`allowed`),
  `rateLimitType` (the window just used, `five_hour`), `resetsAt` (seconds since the epoch),
  `overageStatus`, `isUsingOverage` and `unifiedWindows`: an object with one entry per gauge,
  `{"five_hour": {"utilization": 0.74, "resetsAt": ...}, "seven_day": {...}}`. WxClaude reads
  `utilization` as a fraction (0.74 = 74 %), see `open-questions.md`.
- `result`: `result` (final text), `subtype`, `usage` (`input_tokens`, `output_tokens`,
  `cache_creation_input_tokens`, `cache_read_input_tokens`, plus details), `duration_ms`,
  `total_cost_usd` (a cost at list price, whatever the subscription), `num_turns`,
  `modelUsage` (per model, with `contextWindow`), `permission_denials`.
- `prompt_suggestion`: a predicted next prompt, after `result`.
- The effort is **not** reported by the stream: use the one that was requested.
- Read stdout and stderr continuously (a full pipe blocks the CLI), lines can be very long, and
  read until the end of the process before saying the turn is over.

## Session files

`~/.claude/projects/<folder>/<session-id>.jsonl` (`CLAUDE_CONFIG_DIR` is honoured). The folder
name is an encoding of the working folder that cannot always be decoded: read the `cwd` field of
the entries instead. One JSON object per line; interesting entries have `type` `user` or
`assistant` and a `message`, a `sessionId`, a `cwd`, a `timestamp`.

- Assistant entries carry, at the top level of the entry (not in `message`), `effort` and
  `perTurnEffort` (`low`, `medium`, ... as seen on the existing sessions). Since the alternative agent may have sent the message, the effort of the last
  answer does not tell which agent is the conversation's: WxClaude remembers the main agent itself.
- Identical consecutive assistant entries exist: remove duplicates.
- Noise to hide: the answer "No response requested." and the prompt "continue".
- Messages whose model is `<synthetic>` can carry real information (for example the message that
  a usage limit was reached); keep them, they have no model and no effort.
- A user entry holding only a `tool_result` has no text of its own.
- The title is written to the file by the CLI, asynchronously; a rename adds a `custom-title`
  entry with `customTitle` (repeated many times in a long session: the last one wins, and it takes
  precedence over a generated title).
- Other entry types seen, ignored by `core/session_reader.py`: `attachment`, `queue-operation`,
  `last-prompt`, `mode`, `cost-state`, `atis-latch`. Entries with `isMeta` or `isSidechain` are
  not part of the conversation. The `permissionMode` field is on user entries.
- The reader (`read_session`) skips lines that are not valid JSON (the CLI may be writing one).
- Tasks of a session (verified on a real folder): `~/.claude/tasks/<session-id>/<id>.json` with
  `id`, `subject`, `description`, `activeForm`, `status` (`pending`, `in_progress`, `completed`),
  `blocks` and `blockedBy` (lists of identifiers), `metadata` (free); the folder also holds a
  `.lock` file, which is not a task. WxClaude only reads them.