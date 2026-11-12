# What we know about the Claude Code CLI

Facts gathered while designing WxClaude (CLI 2.1.286 at the time). Check again if the version
changes a lot. Only what was tested or read in the documentation is stated here.

## Running it

- Non-interactive: `claude -p --input-format stream-json --output-format stream-json --verbose`
  plus a permission channel (see "Permission channels"). `--verbose` is required with `stream-json`.
- Prompt: one JSON line on stdin (`{"type": "user", "message": {"role": "user", "content": "..."}}`),
  no command-line length limit (verified). stdin stays open until the `result` line, then is
  closed: the process ends (verified with both channels).
- One process per message; the conversation continues with `--resume <id>`.
- The application chooses the conversation id: `--session-id <uuid>` for the first message
  (verified: the session gets that id), `--resume <uuid>` afterwards. A branch: `--resume <a> --fork-session --session-id <b>` (see "Branch of a session").
- Per message: `--model` (aliases `haiku`, `sonnet`, `opus`, `fable`, or a full name), `--effort`
  (`low`, `medium`, `high`, `xhigh`, `max`), `--permission-mode` (`manual`, `acceptEdits`,
  `plan`, `auto`, `dontAsk`, `bypassPermissions`), `--allowedTools` (rules the CLI may use without
  asking, e.g. `Bash(git *)`), `--tools` (the tools that exist at all).
- `--include-partial-messages` gives partial text; without it every block arrives complete (this is
  what the display relies on). `--no-session-persistence` would prevent resuming.
- The CLI uses the login of the user who runs it: run WxClaude in the user's own session.
- The permission mode `auto` and `bypassPermissions` do not take effect from project settings,
  only from user settings or the command line.

## State and sign-in (measured)

- `claude --version` prints `2.1.286 (Claude Code)`.
- `claude auth status` prints JSON and exits 0 when logged in, 1 when not. Logged in: `loggedIn` true,
  `authMethod` (`claude.ai`), `apiProvider`, `configDirectory`, `projectsDirectory`, `email`, `orgId`,
  `orgName`, `subscriptionType` (`pro`). Not logged in: `loggedIn` false, `authMethod` `none`. With
  `--text`: "Not logged in. Run claude auth login to authenticate." It asks nothing and opens nothing.
  An empty `CLAUDE_CONFIG_DIR` gives the not logged in answer without touching the real sign-in.
  Measured 2026-11-12 (CLI 2.1.286, no model call): with an empty `CLAUDE_CONFIG_DIR` and an
  `ANTHROPIC_API_KEY` in the environment (a made-up key) it says `loggedIn` true, `authMethod` `api_key`,
  `apiKeySource` `ANTHROPIC_API_KEY`, exit 0: a key in the environment counts as logged in. The key is not
  checked. It sees the environment of the process that runs it, not what WxClaude adds to a launch for a
  provider (`launch.py`): so WxClaude does not ask it when the default agent uses another provider.
- `claude auth login` has `--claudeai` (the subscription, the default), `--console` (Anthropic
  Console, API billing), `--sso` and `--email <email>` (pre-fills the address on the sign-in page);
  `logout` and `setup-token` are in the CLI reference.
- **`claude auth login --claudeai` with no terminal** (measured three times, in an empty
  `CLAUDE_CONFIG_DIR`, once from a folder never used before; input from `/dev/null`, output to a file):
  it prints `Opening browser to sign in…`, a line `If the browser didn't open, visit: https://claude.com/cai/oauth/authorize?...`
  and `Paste code here if prompted > ` (no line break), opens the browser by itself, then, once the
  user has pressed *Authorize*, prints `Login successful.` and ends by itself; `auth status` then says
  logged in (`claude.ai`, `pro`) in that folder, and `auth logout` there (`Successfully logged out
  from your Anthropic account.`) brings back `loggedIn` false (exit 1). No code was ever needed:
  the browser comes back to a local port the CLI listens on. **The process must stay alive until the
  user has authorized**: killed before (twice, when it was started in the background of a tool call that
  ended), the browser ends on "localhost refused the connection" / `ERR_CONNECTION_REFUSED`.
- No question was asked on the output, neither about the e-mail address (typed in the browser page) nor
  about the working folder. A user remembers being asked to trust the folder before the browser
  opened, after running `claude auth login`; that was not reproduced with the output redirected, so
  it may be a screen the CLI draws only in a real terminal. The exit code of `auth login` was not
  read. `--email` with `--claudeai` was not tried.
- An expired login in a conversation: the CLI writes, in `-p` mode, a synthetic assistant message
  (`model` `<synthetic>`, no token used) with the text `Failed to authenticate: OAuth session expired
  and could not be refreshed`, `isApiErrorMessage` true and `"error": "authentication_failed"`, for
  every message sent, until the user signs in again (read in a session file). WxClaude shows it in
  the conversation like any answer.

## Permission modes (from the documentation)

| Mode | Runs without asking |
|---|---|
| `manual` (`default` in settings) | reads only |
| `acceptEdits` | reads, file edits, common file commands (`mkdir`, `touch`, `mv`, `cp`, ...) |
| `plan` | reads, plus commands approved by the classifier when auto mode is available |
| `auto` | everything, with background safety checks by a classifier |
| `dontAsk` | reads in the working folders and pre-approved tools; anything else is denied |
| `bypassPermissions` | everything (not offered by WxClaude) |

## Permission channels

The CLI decides when a tool needs a permission; the host only answers. Without a channel, `-p`
denies at once (`permission_denied` system line, failed tool result); `--permission-prompts none`
does the same on purpose.

Tests: CLI 2.1.286, Windows, `haiku`, effort `low`, 2026-10-22, empty folder, prompt on stdin.
`[test]` = observed, `[doc]` = documentation only, `[not tested]`.

### Retained: stdio control protocol and PermissionRequest HTTP hook

| | Stdio control protocol (`stdio`) | PermissionRequest HTTP hook (`hook`) |
|---|---|---|
| Status in WxClaude | implemented, default | implemented (`hook_channel.py`), chosen in Preferences > Claude, checked with the real CLI through the runner (allow, deny) |
| Flags | `--permission-prompt-tool stdio` | `--settings '{"hooks": {"PermissionRequest": [{"hooks": [{"type": "http", "url": "http://127.0.0.1:<port>/<token>", "timeout": <seconds>}]}]}}'` |
| Channel | JSON lines, CLI stdout and stdin | HTTP POST from the CLI to a local server; the response is held until the user answers |
| Needs besides the process | nothing | an HTTP server on `127.0.0.1` |
| Request | `control_request`: `request_id`, `request` {`subtype` `can_use_tool`, `tool_name`, `input`, `description`, `tool_use_id`, `blocked_path`, `permission_suggestions`} | POST body: `cwd`, `hook_event_name`, `permission_mode`, `permission_suggestions`, `prompt_id`, `session_id`, `tool_input`, `tool_name`, `transcript_path`; no `tool_use_id` (the documentation lists it), no `description`, no `blocked_path` [test] |
| Answer allow | `control_response` `{"subtype": "success", "request_id", "response": {"behavior": "allow", "updatedInput": <input>}}` | `{"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": "allow"}}}`; file written in the same turn [test]; WxClaude leaves `updatedInput` out when it is the input of the request |
| Answer deny | same, `{"behavior": "deny", "message": "<text>"}`; Claude gets the text as the tool result | `{"behavior": "deny", "message": "<text>"}`; Claude gets the text as the tool result [test]; the CLI still sends `permission_denied` (`decision_reason_type` `hook`, `decision_reason`) and lists it in `result.permission_denials` [test] |
| Other answer fields | not tested | `updatedInput`, `updatedPermissions`, `interrupt` [doc, not tested]; `decision.rule` appears in one documentation page [not tested] |
| Waiting time | no limit known; closing stdin cancels the question [doc] | `timeout` in seconds, default 600 for most events [doc]. Expiry (`timeout` 10, no answer) [test]: the CLI waited, then denied as a plain `-p` denial (`permission_denied` without `decision_reason_type`, "you haven't granted it yet"), result `success`, Claude asks the user to approve; indistinguishable from a denial in the stream |
| Switch of channel between two messages of a conversation | `--resume` works, context kept [test] | same [test] |
| Mode `plan` | host receives `ExitPlanMode` (`input.plan`, `input.planFilePath` [test]), then the `Write` request; after allow the file is created [test] | hook never called; Claude writes a plan file in `~/.claude/plans/`, has no tool to submit it [test] |
| Mode `dontAsk` | host never called; `permission_denied` with `decision_reason_type` `mode`; Claude tries `Bash` [test] | same [test] |
| Question tool `AskUserQuestion` | host receives it (`display_name`, `input`, `requires_user_interaction`, `subtype`, `tool_name`, `tool_use_id`); `input.questions[]`: `question`, `header`, `options[]` (`label`, `description`), `multiSelect`; answer `updatedInput` `{"questions": <same>, "answers": {"<question>": "<label>"}}`; Claude gets `Your questions have been answered: "<question>"="<label>"` [test] | tool absent (`ToolSearch` finds nothing) in `default` and `plan`; Claude asks in plain text [test] |
| Suggested rule for `Write` | `setMode` `acceptEdits`, destination `session` [test] | same [test] |
| Documentation | only through the Agent SDK (`canUseTool`); the flag value `stdio` is not in the CLI reference | hook type `http` and decision fields documented; the hooks reference says `PermissionRequest` does not fire in `-p` (page not read in full), the headless page says a `PermissionRequest` hook can approve in `-p`; observed: fires [test] |

Differences in one line: the hook has no `AskUserQuestion`, no `ExitPlanMode`, no plan-mode
request, no `description` or `blocked_path`, and needs a local HTTP server; the stdio protocol has
all of them and needs nothing else. `dontAsk` is the same for both: nothing asks.

### Not retained

- **`PreToolUse` hook returning `defer`**: runs before rules and mode, so the application decides which calls need a permission; one stop and one resume per question. [not tested]
- **MCP permission prompt tool** (`--permission-prompt-tool mcp__<server>__<tool>`): needs an MCP server (PyPI `mcp`, many dependencies), request and answer contract not in the pages read, 30 s wait for the server. [not tested]

### Stdio: rules and answers

- The suggestions are rules to add (`{"type": "addRules", "rules": [{"toolName": "Bash",
  "ruleContent": "touch x"}], "behavior": "allow", "destination": "localSettings"}`), directories,
  and a permission mode.
- Destination `localSettings` = `.claude/settings.local.json` in the CLI. In `-p` the host writes it:
  WxClaude writes the *allow* rule (`permissions.allow`); the CLI then does not ask any more, in
  this message and the next ones.
- Rule in `.claude/settings.local.json` [test]: `allow` runs without a question, `deny` refuses
  without a question (`permission_denied`), `ask` asks (even with a matching allow rule).
- Merge order across the settings files: deny, ask, allow; a bare `deny` rule removes the tool from
  Claude's context.
- Windows: the personal file stays in the `.claude` folder of the workspace (other systems: root of
  the git repository).
- Some commands need no answer (`echo` runs under `manual`).

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

- `system` / `compact_boundary` (checked with `/compact` through `-p`, 2026-11-11): after `system` /
  `status` lines (`status` `compacting`, then `compact_result` `success`) and the `init` line comes
  `compact_metadata`: `trigger` (`manual` or `auto`), `pre_tokens`, `post_tokens`, `duration_ms`,
  `cumulative_dropped_tokens` and the identifiers of the messages kept. In the stream the keys are in
  snake case; the session file has them in camel case (`compactMetadata`).
- `system` / `init` gives the mode the CLI really uses (measured with haiku, 2026-11-11, no provider):
  asked `manual` gives `default`; `acceptEdits`, `plan` and `dontAsk` keep their name; **`auto` gives
  `default`** (the mode is not applied, even with Claude).
- MCP servers (measured 2026-11-11 with a throwaway stdio server, haiku, CLI 2.1.286): `system` / `init`
  lists them in `mcp_servers` (`name`, `status`, `source`: `user`, `local`, `project`, `claudeai`).
  A server that exits at once is `failed`; one that takes 25 s to answer `initialize` is `pending` and
  its tool is "No such tool available" for that message (each message is a new process, so it starts
  again every time); a tool call of 130 s completes (no time-out met). A server declared with
  `claude mcp add` in scope `local`, or in the `.mcp.json` of the project, is not loaded in a restricted
  launch (`--setting-sources user`); one of scope `user` is. In an approved folder the `.mcp.json` servers
  connect without asking. The permission question of an MCP tool (`mcp__<server>__<tool>`) reaches both
  channels, with the suggested rule `mcp__<server>__<tool>`, and an allow rule in
  `.claude/settings.local.json` silences it.
- `system` / `init`: `session_id`, `model`, `permissionMode`. `system` / `thinking_tokens`
  (`estimated_tokens`). `system` / `permission_denied` (`tool_name`, `tool_use_id`, `message`,
  `decision_reason_type`).
- `assistant`: `message.content[]` with **one block per message** (`thinking`, `tool_use` or
  `text`), `message.model`.
- `user`: carries the `tool_result` blocks (`tool_use_id`, `is_error`, `content`).
- `rate_limit_event` (verified, one per message): `rate_limit_info` with `status` (`allowed`),
  `rateLimitType` (the window just used, `five_hour`), `resetsAt` (seconds since the epoch),
  `overageStatus`, `isUsingOverage` and `unifiedWindows`: an object with one entry per gauge,
  `{"five_hour": {"utilization": 0.74, "resetsAt": ...}, "seven_day": {...}}`. `utilization` is a
  fraction (0.74 = 74 %): verified on 2026-10-23, the stream said 0.37 and 0.62 and `/usage`, a few
  minutes later, 39 % and 63 %.
- Early warnings of Claude Code itself (read in the code of the CLI 2.1.286, not documented): the
  5-hour gauge warns from 90 %; the weekly gauge from 75 %, 50 % and 25 %; a warning (status
  `allowed_warning`) is only given when the share of the window already elapsed is at most 72 %
  (5 hours), 60 %, 35 % and 15 % (week) respectively, that is when the usage goes faster than time.
  WxClaude announces each of these thresholds (`core/claude/usage.py`, `ALERT_THRESHOLDS`), without
  the time condition.
- `result`: `result` (final text), `subtype`, `usage` (`input_tokens`, `output_tokens`,
  `cache_creation_input_tokens`, `cache_read_input_tokens`, plus details), `duration_ms`,
  `total_cost_usd` (a cost at list price, whatever the subscription), `num_turns`,
  `modelUsage` (per model, with `contextWindow`), `permission_denials`.
- **`total_cost_usd` and `modelUsage` are the total of the session since its creation, not the
  cost of the message** (verified 2026-10-23, CLI 2.1.286, haiku, effort `low`: 0.0460, 0.0500 and
  0.0530 for three messages of one session, which cost about 0.004 and 0.003 each). The first
  message of a branch starts from the total of the conversation it copies (0.0530, then 0.0558).
  The `usage` field is per message (its token counts differ from message to message). The session
  file holds the same total in its last `cost-state` entry (`totalCostUSD`), so the cost of a
  message is the total it reports minus the total before it: 0 for a session that does not exist
  yet, the `cost-state` of the file for one that is opened, the total of the conversation it
  copies for a branch (`core/claude/usage.py`, `UsageTracker`).
- **`duration_ms` includes the time the user takes to answer a permission question** (verified
  2026-10-23, CLI 2.1.286, haiku, effort `low`, stdio protocol: a question answered after 30 s gave
  `duration_ms` 34.4 s, `duration_api_ms` 3.7 s and, in the session file, `totalDuration` 35.0 s,
  `totalAPIDuration` 3.7 s, `totalToolDuration` 0.6 s). The time of work is therefore
  `duration_ms` minus the time the question was open (measured by WxClaude), or
  `totalAPIDuration + totalToolDuration` in a file; the statistics use that.
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
- Noise to hide: the answer "No response requested.", the prompt "continue" and the summary written
  when the CLI compacts the conversation (a `user` entry with `isCompactSummary`, preceded by a
  `system` entry of subtype `compact_boundary` whose `compactMetadata` gives `trigger`, `preTokens`,
  `postTokens` and `durationMs`; seen in a real session).
- Messages whose model is `<synthetic>` can carry real information (for example the message that
  a usage limit was reached); keep them, they have no model and no effort.
- A user entry holding only a `tool_result` has no text of its own.

### Gauges without a message (verified 2026-10-23, CLI 2.1.286)

`claude -p "/usage" --output-format json` (the `/` must reach the CLI as is) answers at once, with
no model call: `total_cost_usd` 0, `num_turns` 0, no token. The `result` is text for people, in
English, for example:

```
Current session: 96% used · resets Oct 23, 1:50pm (Europe/Paris)
Current week (all models): 67% used · resets Oct 26, 1am (Europe/Paris)
```

followed by a breakdown "What's contributing to your limits usage?" (local, approximate). Notes:

- It is **text**: whole percentages, the reset in local time, no structured data, and the stream has no
  `rate_limit_event` for it. The label "Current session" is the 5-hour window. Parsing it depends on
  wording the CLI may change.
- Each call writes a session file in the project folder, unless `--no-session-persistence` is given
  (verified: with it, no session file; only the project folder and its `memory` folder are made).
  Without it the sessions would appear in the list of conversations of the workspace.
- `/status` is a local command of the same kind, without the gauges.
- `claude auth status` and the other subcommands do not give the gauges.

How WxClaude uses it (`ClaudeRunner.read_usage`, `core/claude/usage_text.py`,
`core/claude/gauge_schedule.py`; `interface.md`, "Status bar"):

- The command is `-p /usage --no-session-persistence --output-format json`, run without standard
  input in the folder of the workspace (without a workspace nothing is read). Only the lines
  "Current session" (5-hour window) and "Current week (all models)" (weekly window) are read; the
  reset time is local time with no year (the nearest matching date), the zone in brackets is ignored.
  Anything else is skipped: a text without these lines gives no gauge and the known values stay.
- The process is stopped after 15 seconds, or at once by Interrupt. A CLI that is missing, fails or
  does not answer is not reported: nothing is said and the next try waits 1, 2, 4, 8 then 10
  minutes. The reading shares the single process of the runner, so it never runs with a message.
- It is read when the application starts, when a first workspace opens, and by a timer of one
  minute when a gauge is unknown or past its reset time (the value shown is then out of date). A
  reading is not asked for when a window is opened: the usage dialog shows what is known.

### Branch of a session (verified 2026-10-23, CLI 2.1.286, haiku, effort `low`)

`claude -p --resume <a> --fork-session --session-id <b> --name <name>` with a prompt:

- The new session gets the identifier `b`, chosen by the application as with `--session-id`
  alone, and the name given with `--name`.
- The file of `b` holds the whole history of `a` (the same entries, with the same `uuid`, their
  `sessionId` rewritten), then the new message. The title of `a` is not copied. No field names
  the session it comes from.
- `a` is left as it is. Claude keeps the context (it answered with a word given in `a`) and the
  prompt cache is read.
- The `result` of that first message reports in `total_cost_usd` and `modelUsage` the total of
  `a` plus its own cost (0.0538 $ for a message that cost 0.0039 $): every `result` reports the
  total of the session (see "The stream").
- A branch only exists through a message: WxClaude makes it with the first message of the branch.

### Deleting a session (documentation, CLI 2.1.286)

No command deletes one session: not a command of a session, not the `/resume` picker; `claude
purge` deletes a whole project, `claude rm` only a background session. The CLI removes a
transcript after `cleanupPeriodDays` (30 by default), and the documentation lets the user delete
its application data by hand. What it keeps of a session: `projects/<folder>/<id>.jsonl`, the
folder `projects/<folder>/<id>/` (subagents, large tool results), `file-history/<id>/` and
`tasks/<id>/`. WxClaude moves those to the Recycle Bin (`claude_projects.session_paths`).

### Name of a session (verified 2026-10-23, CLI 2.1.286, haiku, effort `low`)

The name is the last `{"type": "custom-title", "customTitle": "...", "sessionId": "..."}` entry of
the session file (`ai-title` / `aiTitle` is a title the CLI generated, `custom-title` wins). Three
ways to change it, all seen working:

- **`/rename <name>` as the prompt of `claude -p --resume <id>`** (the name must reach the CLI
  as is: no path conversion of the leading `/`). The result line says `Session renamed to: <name>`
  (`local_command` `rename`), the call takes about 60 ms and sends nothing to the model, so it costs
  nothing. The CLI appends a `custom-title` entry (and an `agent-name` one).
- **`--name <name>`** (`-n`) on a message, the first one (with `--session-id`) or a later one
  (with `--resume`): it appends a `custom-title` entry. The stream starts with a system line
  `{"type": "system", "subtype": "session_title_changed", "title": "<name>"}`.
- **Appending a `custom-title` line to the file by hand**: the next `--resume` reports the new
  title in `session_title_changed`. Possible, but the file belongs to the CLI (it may be open in
  another process), so WxClaude does not write it.
- The title is written to the file by the CLI, asynchronously; a rename adds a `custom-title`
  entry with `customTitle` (repeated many times in a long session: the last one wins, and it takes
  precedence over a generated title).
- `cost-state` entries (one per turn, in sessions of `-p` and interactive ones) hold the totals of
  the whole session so far: `totalCostUSD`, `totalDuration`, `totalAPIDuration`,
  `totalToolDuration` (milliseconds), `totalLinesAdded`, `totalLinesRemoved`, `startTime` and
  `modelUsage` (per model: `inputTokens`, `outputTokens`, `thinkingTokens`,
  `cacheReadInputTokens`, `cacheCreationInputTokens`, `costUSD`). Read by `core/claude/cost_state.py`.
  Nearly every entry has a `timestamp`. A branch made with `--fork-session` has no `cost-state` of
  the copied history: its first one already includes the totals of the conversation it copies.
- Other entry types seen, ignored by `core/claude/session_reader.py`: `attachment`, `queue-operation`,
  `last-prompt`, `mode`, `atis-latch`. Entries with `isMeta` or `isSidechain` are
  not part of the conversation. The `permissionMode` field is on user entries.
- The reader (`read_session`) skips lines that are not valid JSON (the CLI may be writing one).
- Tasks of a session (verified on a real folder): `~/.claude/tasks/<session-id>/<id>.json` with
  `id`, `subject`, `description`, `activeForm`, `status` (`pending`, `in_progress`, `completed`),
  `blocks` and `blockedBy` (lists of identifiers), `metadata` (free); the folder also holds a
  `.lock` file, which is not a task. WxClaude only reads them.

## Other providers (verified 2026-11-09, CLI 2.1.286, a fake local server)

Measured with the real CLI in an empty `CLAUDE_CONFIG_DIR` against two fake servers that log the
requests and answer with a short stream (no model, nothing paid). Not yet measured with a real
model (tools, resuming a session of another provider): see `open-questions.md`.

- **No sign-in is needed.** With `ANTHROPIC_BASE_URL` and `ANTHROPIC_AUTH_TOKEN` (sent as
  `Authorization`), `claude -p` runs and the `system/init` line says `apiKeySource: "none"`.
- **Precedence of `env`**, strongest first: `--settings` (inline JSON or file), the `env` key of
  `.claude/settings.local.json`, then the environment of the process. The `env` of the shared
  `.claude/settings.json` also beat the process (the order between the two project files and the
  general file was not tried). So a provider chosen by WxClaude in the environment of the process
  is overridden by a project file that sets the same variable; `--settings` is not.
- **No trust is needed in `-p`**: the `env` of both project files was applied in a folder that was
  never trusted. A cloned repository can therefore point the CLI to another server.
- **The variables are merged key by key.** A project file that sets only `ANTHROPIC_BASE_URL`
  leaves `ANTHROPIC_AUTH_TOKEN` of the process in place, and the token **is sent to the URL of the
  file** (seen in the `Authorization` header received by the fake server). With `--settings`
  setting only the URL, the URL of `--settings` wins and the token of the process is still used.
  So the URL must always be given by `--settings`; the token can stay in the environment of the
  process (not on the command line).
- **The tools of Claude see the key.** A `Bash` command run by the CLI printed
  `ANTHROPIC_AUTH_TOKEN` and `ANTHROPIC_BASE_URL` as set in the environment of the process: the
  CLI does not remove them from the environment of its tools. A prompt injection (text in a file
  that Claude reads) can therefore ask Claude to show or send the key. Not measured: the
  `PowerShell` tool (it was not available in that run), other variables (`ANTHROPIC_API_KEY`), a
  way to hide them (settings of the CLI such as a list of variables to remove).
- **Models.** `--model` takes any name and sends it as is; `ANTHROPIC_DEFAULT_HAIKU_MODEL` (and the
  `SONNET` and `OPUS` ones) redirect the aliases. For a name the CLI does not know, stderr gets
  `[claude-code:unrecognized_model] {...}`; it is not an error (exit code 0).
- **Effort and thinking.** `--effort low` is sent as `output_config: {"effort": "low"}`; `thinking`
  is `{"type": "adaptive"}` or `{"type": "enabled", "budget_tokens": ...}`. Whether a given server
  accepts them is not known.
- **Cost.** `total_cost_usd` and `modelUsage[...].costUSD` are computed by the CLI from its own
  price list, not by the server. For an unknown model `costBasis` is `"unknown"` and a figure is
  still given (it is not a real cost). `modelUsage` is keyed by the name sent to the server, and
  `canonicalModel` holds it as is when it is not a Claude one.
- **Other stderr lines.** With a server that is not the official one, the CLI writes a notice about
  the billing of the classifier of the auto mode on stderr. It is not an error.

### DeepSeek, first contact (measured 2026-11-09, CLI 2.1.286, `deepseek-v4-flash`)

`https://api.deepseek.com/anthropic`, key as `ANTHROPIC_AUTH_TOKEN`, empty work folder, temporary
`CLAUDE_CONFIG_DIR`, prompt "Reply with the single word: ok", the provider launch of WxClaude
(`provider_settings`, `provider_environment`).

- **It works**: exit 0, `result` "ok", 1 to 1.4 s, `system/init` names `deepseek-v4-flash` and
  `apiKeySource` `none`. `ANTHROPIC_AUTH_TOKEN` is accepted (the server takes the Bearer header).
- **`--effort low` is accepted** (same answer with and without it): `send_effort` can stay on.
- **A `thinking` block comes first**, with an empty text and a UUID as signature, then the `text` block.
  Nothing to display; to look at in P2.4 (a history written by DeepSeek sent back to Claude).
- **Stderr**: `[claude-code:unrecognized_model] {"model":"deepseek-v4-flash",...}` (a notice, exit 0).
- **The figures are not a cost**: 16,305 input tokens for a one word prompt (system prompt and tools),
  `total_cost_usd` 0.0816, `costBasis` `unknown`, `provider` `firstParty`, `contextWindow` 200000 (the
  CLI's guess). The dollars are Claude's price list applied to DeepSeek's tokens.
- **A wrong key (401) is retried**: the stream carries `system` / `api_retry` lines
  (`attempt`, `max_retries` 10, `retry_delay_ms` 600, 1166, 2283, 4202, 9102, 17571, 37085..., 
  `error_status` 401, `error` `authentication_failed`) and no `result` for minutes (more than 120 s
  without an end). WxClaude now reads `api_retry` (`ApiRetry`) and, for a 401 or a 403, kills the CLI
  at the first one and tells the user (measured with the real runner and a wrong key: stopped in
  0.8 s, an error box "The server refused the credentials (error 401)..."). The other statuses are
  retried by the CLI; WxClaude says each retry with its reason (`interface.md`, "Silent retries").
- The names `deepseek-v4-flash` and `deepseek-v4-pro` are the ones the server gave; `deepseek-flash`
  (typed in the provider by the user) was not tried.

### DeepSeek with the Claude login, and switching (measured 2026-11-10, CLI 2.1.286)

With the real configuration of the user (logged in to claude.ai, subscription) and the real runner of
WxClaude; `haiku` low for Claude, `deepseek-v4-flash` low for DeepSeek; one session, a work folder
made for the test, prompts of one sentence.

- **No login and no subscription needed** for DeepSeek (first section above, empty configuration:
  `apiKeySource` `none`). **With a login, the token of the provider wins**: the CLI answers with DeepSeek
  and writes on stderr `⚠ claude.ai connectors are disabled because ANTHROPIC_API_KEY or another auth
  source is set and takes precedence over your claude.ai login`. It is a notice (exit 0); WxClaude
  does not take it for the cause of a failure (`progress.py`).
- **Switching in one conversation works**: Claude (haiku), then DeepSeek (`--resume` of the same
  session), then Claude again (`--resume`): the three answered, and the secret word given in the
  first message was recalled by DeepSeek and by Claude afterwards. So one session file for all the
  providers is right; the fall-back (a branch) is not needed for this pair.
- **The cache**: Claude wrote 33,449 tokens in its cache when it came back (read: 0), so the cache
  of the first Claude message was lost, as expected. DeepSeek reported tokens read from its own
  cache (87,936 then 29,696 of 29,302 / 209 new input tokens): its caching is automatic.
- Not tried: a history with a long thinking block of Claude sent to DeepSeek, a Plan-mode session.

### DeepSeek, tools and permission modes (measured 2026-11-10, CLI 2.1.286, `deepseek-v4-flash` low)

The real runner of WxClaude, stdio channel, an empty work folder holding `note.txt`.

- **Tools work**: `Read` (no question, answer "alpha"), `Write` (a question, allowed: the file was
  made), `Bash` (`echo hi` ran with no question, as a read-only command; a command that changes
  something was not tried), `ExitPlanMode`. The `ASK` events are the usual ones; `suggested_rule` is
  empty for `Write`.
- **The scrub forces the permission mode** (`CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1`, on by default for a
  provider): stderr says `Permission mode forced to default — CLAUDE_CODE_SUBPROCESS_ENV_SCRUB is set
  (allowed_non_write_users hardening). Declare allowedTools explicitly, or set
  CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=0 to opt out`, `system/init` gives `permissionMode` `default`, and the
  modes of the agent do not apply: `acceptEdits` asked before writing, `auto` and `dontAsk` asked, and
  `plan` wrote the file after a question (no plan at all). Only `manual` is what it says.
- **Without the scrub every mode is honoured**: `acceptEdits` and `auto` wrote with no question,
  `dontAsk` refused `Write` and `Bash` (`denied`, reason `mode`) and said so, `plan` wrote the plan to
  `~/.claude/plans/<name>.md`, asked `ExitPlanMode` (with the plan) and then, allowed, wrote the file.
- `--allowedTools Read` does not lift the forced mode (`plan` and `acceptEdits` tried). Other values were
  not tried.
- The mode really used is in `system/init` (`SessionInit.permission_mode`), so a difference with the
  mode asked can be detected.
- Not tried yet: the hook channel, a structured question (`AskUserQuestion`), `WebSearch`, a `Bash`
  command that changes something.
- **The key is visible to `Bash` without the scrub** (measured: `echo len=${#ANTHROPIC_AUTH_TOKEN}` gave
  `len=35`). **The sandbox does not help on native Windows**: the documentation says it runs on
  macOS, Linux and WSL2 only; with `sandbox.enabled` and `sandbox.credentials.envVars` `deny` for the
  variable, the CLI wrote `Sandbox disabled: ... the Windows sandbox is not active on this session
  (feature gate off). Commands will run WITHOUT sandboxing` and the length was still 35. (With the
  scrub the same command was refused by the permission rule: "Contains expansion"; the scrub itself
  was measured earlier.)

### DeepSeek through the relay of WxClaude (measured 2026-11-10, CLI 2.1.286)

The real runner, `deepseek-v4-flash` low, the relay in the same process
(`core/security/key_relay.py`), `ANTHROPIC_BASE_URL` the relay and `ANTHROPIC_AUTH_TOKEN` its token, no
scrub.

- **Everything works through the relay**: a plain answer (2 s), `Read`, `Write` (with its question), and the
  stream of events. Nothing was cut or held back.
- **The permission modes are applied**: `system/init` gave `acceptEdits` and `plan`; `acceptEdits` wrote
  with no question, `plan` wrote the plan to `~/.claude/plans`, asked `ExitPlanMode` and, refused, did not
  write the file. Without the relay and with the scrub these modes were forced to manual.
- **The key is not in the CLI**: `Bash` printed `len=43` for `ANTHROPIC_AUTH_TOKEN` (the token); the key
  has 35 characters.
- **The CLI closes its connections to the relay with a reset** (`WinError 10054`) when it ends a
  message: it is not an error and the server does not report it.

### Folders never trusted and credentials (documentation read on 2026-11-09, not measured)

From the pages Permissions ("What runs before you trust a folder"), Settings reference (`env`,
`apiKeyHelper`), Environment variables and Sandboxing of the official documentation:

- **`claude -p` never shows the trust dialog, and uses what the repository supplies**: the hooks of
  its settings files, its `env` block, helper commands such as `apiKeyHelper` and `awsAuthRefresh`,
  and the servers of its `.mcp.json` (connected without asking). The `allow` rules and
  `additionalDirectories` of `.claude/settings.json` are not used (stderr: `this workspace has not
  been trusted`). So a repository cloned from elsewhere can run commands through a hook.
- **What the documentation proposes before `claude -p` in a repository one did not write**:
  `--setting-sources user` (neither the settings files of the project nor its `.mcp.json` are
  read); `--bare` (no hooks, skills, commands, subagents, plugins or `.mcp.json` servers of the
  project; its `env` and `awsAuthRefresh` still apply and `apiKeyHelper` is read only from
  `--settings`); `--settings '{"disableAllHooks": true}'` (also turns off the hook of the `hook`
  permission channel of WxClaude); an entry in `disabledMcpjsonServers`.
- **`ANTHROPIC_BASE_URL` and `ANTHROPIC_AUTH_TOKEN` are not in the list of the variables that the
  project and local files cannot set** (the list is about paths, telemetry, sign-in and
  accessibility variables). This agrees with the measurement above.
- **`CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1`** (environment of the process) removes credentials from the
  environments of the subprocesses of the CLI: Bash commands, hooks, stdio MCP servers. A
  credential is recognized by the name of the variable or the shape of its value (`ANTHROPIC_API_KEY`
  is listed as removed; `ANTHROPIC_AUTH_TOKEN` is not named: to measure). `GITHUB_TOKEN`, `GH_TOKEN`
  and the proxy variables stay. The CLI keeps the credentials for its own calls. The documentation
  calls it one layer, not the only control. `CLAUDE_CODE_MCP_ALLOWLIST_ENV=1` does the same for
  stdio MCP servers.
- **`apiKeyHelper`** (a shell command, `cmd /c` on Windows, accepted from `--settings`): its output
  is sent as both `X-Api-Key` and `Authorization: Bearer`, cached five minutes
  (`CLAUDE_CODE_API_KEY_HELPER_TTL_MS`) and run again after a 401 or 403. The key then is not in the
  environment of the CLI. The documentation points to it for API credentials, and says the values
  of `env` are plain text in the settings file.
- **The sandbox of the Bash tool does not exist on native Windows** (macOS, Linux and WSL2 only), so
  `sandbox.credentials` (hide variables and files from commands) cannot be used there.
- **Data sent to Anthropic**: `DISABLE_TELEMETRY`, `DISABLE_ERROR_REPORTING` and
  `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` turn off telemetry, error reports, updates and the
  feature flags. Whether the CLI sends any of it when `ANTHROPIC_BASE_URL` points elsewhere is not
  known.

### Measured: restricted run, scrub and key helper (2026-11-09, CLI 2.1.286, fake server)

Project used: a hook (writes a file), an `env` with another URL, a `.mcp.json` server (writes a
file when started), a `CLAUDE.md`, a command and an agent. The folder was never trusted.

- **Without restriction in `claude -p`**: the hook ran, the command of the `.mcp.json` server was
  started (its status is `failed`, it is not an MCP server, but the command ran), the request went
  to the URL of the project's `env` with the token of the process, and `CLAUDE.md`, the command and
  the agent were loaded.
- **`--setting-sources user`**: none of it. No hook, no server started, the URL of the process is
  used, and `CLAUDE.md`, the commands and the agents of the project are not loaded either (the
  project's instructions are lost in a restricted run).
- **`deny` rules given by `--settings`** together with `--setting-sources user` are applied: the
  `Read` of a denied file answered `File is in a directory that is denied by your permission
  settings`; without the rule the file was read.
- **`CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1`**: the CLI still used the keys (both headers), while a
  `Bash` command and a `PowerShell` command saw `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_API_KEY` and a
  `DEEPSEEK_API_KEY` of the shape `sk-...` as empty. `ANTHROPIC_BASE_URL` stays visible. Without the
  scrub both tools saw all of them. The `PowerShell` tool only existed with
  `CLAUDE_CODE_USE_POWERSHELL_TOOL=1` in this setup.
- **With both `ANTHROPIC_API_KEY` and `ANTHROPIC_AUTH_TOKEN` set**, both headers are sent
  (`x-api-key` and `Authorization: Bearer`) and `apiKeySource` is `ANTHROPIC_API_KEY`.
- **`apiKeyHelper` given by `--settings`** (`echo ...` on Windows): works; `apiKeySource` is
  `apiKeyHelper`; the key is sent in both headers; the tools do not see it because it is in no
  environment. Not measured: a slow helper, the refresh.
### Measured: two `--settings`, and the restricted launch of WxClaude (2026-11-09, CLI 2.1.286, fake server)

- **Two `--settings` are accepted but not merged**: only the last one counts. With a first JSON holding
  an `env` and a hook and a second holding another `env` and another hook, only the second ones were
  applied (also with `--setting-sources user`). WxClaude therefore writes one `--settings`, merged from
  the permission channel and, for a folder not trusted, the rules of the project
  (`core/claude/inline_settings.py`).
- **A project with a hook, an `env` pointing at another URL and a `.mcp.json`, launched through
  `ClaudeRunner`**: not restricted, the hook ran and the request, with the token of the process, went to
  the URL of the project. Restricted (`--setting-sources user`, with the stdio channel and with the
  hook channel), no hook ran and the request went to the URL of the user. (The command of the
  `.mcp.json` did not write its file in this run, restricted or not; the earlier measure above did.)

### Measured: the variables of a provider in the inline `--settings` (2026-11-10, CLI 2.1.286, `haiku` low)

The variables `API_TIMEOUT_MS` and `CLAUDE_CODE_MAX_CONTEXT_TOKENS` of a provider (`providers.md`, field
`env`) are given in the `env` of the inline `--settings`, like the address and the aliases.

- **They reach the process**: `--settings '{"env":{"API_TIMEOUT_MS":"123456",...}}'` and a `Bash` call
  `echo $API_TIMEOUT_MS` print `123456`, with and without `--setting-sources user` (the restricted
  launch). So they apply in a folder that is not trusted.
- **`API_TIMEOUT_MS` is used for the calls to the server**: with `ANTHROPIC_BASE_URL` pointing at a local
  socket that accepts and never answers, `API_TIMEOUT_MS` set to 3000 gave three `api_retry` lines (error
  `unknown`, no status) within 25 seconds; without it, none in 25 seconds (the default wait is much longer).
- **Not measured**: that `CLAUDE_CODE_MAX_CONTEXT_TOKENS` changes what the CLI sends or when it compacts
  (only that the variable reaches the process), and the effect on a real local model.
