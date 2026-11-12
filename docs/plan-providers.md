# Plan: AI providers and trusted folders

For a new session. Read, in this order: `CLAUDE.md`, `roadmap.md`, `working-rules.md`, then
`providers.md` and `security.md` (the specifications this plan builds), `claude-cli.md` (the facts,
"Other providers" and the sections after it) and the entry "Other AI providers" of `open-questions.md`.

The work has three parts, built in this order. Each step ends in a state where the full suite passes
and a commit can be proposed (never made without the user's approval).

| Part | Needs | Content |
|---|---|---|
| 1 | No server of any kind | Everything that can be written and tested with the fake `claude` and the fake server: security core, providers, launch, presenters, views. |
| 2 | A remote server: the user has a DeepSeek API key | The integration with a real remote provider, the measures left, the adaptations they call for. |
| 3 | A local server: the user installs LM Studio or another | The integration with a local provider, the measures left. |

Status of the steps (update it at the end of every step):

| Step | Status |
|---|---|
| P1.1 | done (`core/security/sensitive.py`, committed) |
| P1.2 | done (`core/security/watch.py`, `workspace_state.py`, `ToolSettings` through a `FileGuard`; wired in P1.6a) |
| P1.3 | done (`core/security/restricted.py`, `core/claude/inline_settings.py`, `RunRequest.restricted`, `restricted=` of `rename_session` and `read_usage`; wired in P1.6a) |
| P1.4 | done (`core/config/providers.py`, `core/security/vault.py`, `Agent.provider`, `Settings.providers_path`; `tests/fakes/fake_vault.py`; the Agent dialog keeps the provider but has no list for it until P1.7) |
| P1.5 | core done (`core/claude/launch.py`, `RunRequest.provider`, `Settings.scrub_credentials`, `environment` in the log of the fake `claude`); the callers are wired in P1.6 |
| P1.6a | done (see below) |
| P1.6b | done (`presenters/providers_presenter.py`, `core/config/agent_choices.py` for the Agent dialog, `launch_for` wired in `RunPresenter`, the store in the window; the views are P1.7) |
| P1.6c | done (`data/env_vars.txt` in one language, `core/claude/env_vars.py`, `presenters/env_vars_presenter.py`; the list is partial: the official page was read only as far as `CLAUDE_CODE_NO_FLICKER`, through a summarizer) |
| P1.7a | done (the tabs *Environment variables* and *Security* of the Workspace settings, `ui/env_vars_page.py`, `ui/security_page.py`, `presenters/security_tab_presenter.py`; *Ask me later* removed; the page *Tools* was not moved into its own file, to keep its nine tests) |
| P1.7b | done (`ui/providers_page.py`, `ui/provider_dialogs.py`, the list *Provider* in `ui/agent_panel.py`, the check box of the scrub; models and aliases are typed as text, one model per line; with no provider specified the models of Claude are offered) |
| P1.7c | done (the category *security* (`Trust of the folder`), the cases of `focus.md`, the checklist for NVDA and JAWS in `roadmap.md`) |
| P1.8 | done (the specs moved to `architecture.md`, `interface.md`, `settings.md`, `focus.md`; `providers.md` and `security.md` say they are built; `open-questions.md` and `roadmap.md` updated) |
| P2.0 to P2.7 | not started |
| P3.0 to P3.5 | started: a first test with Ollama and `qwen3:4b` works (`providers.md`, "Measured with a local server"); P3.1 and P3.3 done (a provider without a key, the closed list of variables of a provider, DeepSeek and Ollama at the first start); the measures of P3.2 and P3.4 are left: they need a machine fast enough for a model, and the user's is not |

## Rules for every step

- One shell command per call, never chained. Targeted tests while working; the full suite, `ruff check`,
  `ruff format --check` and `mypy src tests` once, just before proposing a commit (`CLAUDE.md`).
- Every visible text goes through `_()`, with named fields; the French catalog is recompiled after
  each edit. Every control has an accessible name, every dialog an initial focus (`focus.md`: add the
  cases of the new dialogs).
- `core/` and `presenters/` never import `wx`; mypy strict there; a Protocol for each view.
- Docs: when behaviour is built, move the facts from `providers.md` / `security.md` to the files
  that describe what is true (`architecture.md` modules, `interface.md` screens, `settings.md` files
  and keys, `focus.md`), and delete from `open-questions.md` what is settled. User-visible changes
  go to "Unreleased" of `CHANGELOG.md`. **The help (`MakeHelp/`) is not touched unless the user
  asks.**
- Measures with the real CLI: a dedicated work folder and a temporary `CLAUDE_CONFIG_DIR` (so that
  `~/.claude/projects` receives nothing), scripts outside the project, all deleted at the end. A fake
  HTTP server that logs the requests (headers and tools results) and can answer with a scripted tool
  call was enough for part 1: write it again in `Temp` if needed, never in the project.
- A step that needs a decision from the user says so; ask before coding.

## Part 1: without any server

Layout: a new subject `core/security/` (`sensitive.py`, `watch.py`, `restricted.py`, `vault.py`) and
`core/config/providers.py`; presenters and views as the other screens (`architecture.md`).

**P1.1 Sensitive names and masking** (`core/security/sensitive.py`).
- Which names look like a credential (KEY, TOKEN, SECRET, PASSWORD, PASSWD, CREDENTIAL, AUTH...) and
  which redirect the traffic (BASE_URL, PROXY, ENDPOINT, CERT...); a function that masks, in a parsed
  JSON, the values of the keys of the first kind (by a hash). One rule used by the copies of the
  watched files and by the Environment variables tab.
- Done when: unit tests of the rule on real names (`ANTHROPIC_AUTH_TOKEN`, `NPM_TOKEN`,
  `DATABASE_URL`, `HTTPS_PROXY`, `MODEL`...) and of the masking (depth, lists, non-JSON input).
- To settle with the user: the exact lists of names (they are in the code, easy to change).

**P1.2 Watched files** (`core/security/watch.py`, `core/config/workspace_state.py`).
- The default list, the hash (SHA-256), the copy with masked values (`workspaces/<hash>.watch/*.bak`),
  the comparison giving changes (changed, added, removed, absent) and the lines that describe them,
  the `trusted` flag and the watch entries in the workspace file, kept like the other files
  (`jsonstore`). A file absent at approval has no copy.
- **The single writer**: every write of `.claude/settings*.json` goes through one function that checks
  the hash first (a change from outside is returned, not overwritten), writes, and records the new
  hash and copy. Route `SettingsFile.save` (`core/claude/claude_settings.py`) through it.
- Done when: tests in a temporary folder (approve, change, add, remove, absent file, write by
  WxClaude without false alert, write over an external change refused); the Tools tab still works.

**P1.3 Restricted launch** (`core/security/restricted.py`, `core/claude/runner.py`,
`permission_channel.py`, `hook_channel.py`).
- First check with the real CLI and a fake server (cheap, nothing paid): does the CLI accept two
  `--settings`, and do they merge? If not, change `PermissionChannel.arguments()` (the hook channel
  returns the whole `--settings` argument today, `hook_channel.py:110`) so that a channel gives a
  dict of settings and `build_arguments` merges them into the single `--settings`.
- Build the arguments of a restricted run: `--setting-sources user`, the `deny` and `ask` rules read
  from the two project files merged into the inline settings, the permission mode forced to `manual`
  for the message. Missing or damaged project files give no rule.
- Done when: tests of `build_arguments` with the fake, with and without trust, with and without the
  hook channel; a manual run of the real CLI in a booby-trapped dummy folder shows no hook, no server,
  no project `env` (the measure of this session, repeated through WxClaude's code).

**P1.4 Providers and the key** (`core/config/providers.py`, `core/security/vault.py`,
`core/config/agents.py`, `settings.py`, `workspace_state.py`).
- `Provider` (`@dataclass(slots=True)`), the built-in Claude, the store `providers.json` with
  `jsonstore`; `KeyVault` (Protocol) with the DPAPI implementation (`ctypes`, Windows only) and a fake
  for the tests; `key_source` with only `stored` built.
- `Agent.provider` (default `claude`): `to_dict`, `from_dict` (an unknown id falls back to Claude),
  `over()`, the three levels (`default_agent`, `alternative_agent`, the conversation's agent).
- Done when: round trips, a damaged `providers.json`, a key stored then read back and removed, a key
  that cannot be decrypted (another account) giving a clear error, an old settings file without
  `provider` still read.

**P1.5 Launching with a provider** (`core/claude/launch.py` new, `runner.py`).
- A small typed object for what a launch needs (arguments and environment), built from the request,
  the provider, the key and the trust state; `Popen` gets `env=`. The environment: the key as
  `ANTHROPIC_AUTH_TOKEN`, the scrub, the telemetry variables, the inherited `ANTHROPIC_*` and
  `CLAUDE_CODE_USE_*` removed; the inline settings: `ANTHROPIC_BASE_URL` and the aliases. `--effort`
  only if `send_effort`. A new preference for the scrub (check box, on). The stderr notices of a
  third-party server (`unrecognized_model`, the notice about the auto mode) are not errors.
- Done when: `tests/fakes/fake_claude.py` has a scenario that reports the arguments and the
  environment it was given, and the tests assert them for Claude and for a provider, with a key that
  never appears in the arguments.

**P1.6 Presenters** (no `wx`, fake views), in three sub-steps, one commit each:
- **P1.6a Security** (done): `SecurityPresenter` (`presenters/security_presenter.py`) with its wx view
  (`ui/security_view.py`: the offer to approve, which keeps *Keep restricted* as the default button and
  *Ask me later* as Escape; the alert, a `ListDialog` of the changed files with their differences under
  them and the buttons *Accept the changes* / *Restrict the folder*). Wired: the window offers the
  approval once it shows (`WorkspaceLinks.opened`), a folder not approved is launched restricted (the
  messages, the gauges, the rename), the settings files are written through the guard (the Tools tab and
  *Always allow*), and a refused write opens the alert. `WorkspaceState` gets `approval_asked` and
  `existed`. The tests of the window do not open the dialog (fixture `folders_are_trusted`, marker
  `real_security` to opt out). **Until P1.7 there is no tab *Security*** : a folder kept restricted has
  no way back to approved (the dialog says where it will be).
- **P1.6b Providers**: `ProvidersPresenter`, the Agent dialog presenter, and the **provider wiring left
  from P1.5**: `RunPresenter` builds `RunRequest.provider` =
  `ProviderLaunch(store.get(agent.provider), store.key(id) if needed, settings.scrub_credentials)` and
  shows a `KeyVaultError` / `ProviderError` as an error before anything is started. The notice of the
  auto mode on stderr (`claude-cli.md`) is not filtered out of the details of a failure: its exact text
  is not known (only `[claude-code:unrecognized_model]` is).
- **P1.6c Environment variables** (done): `EnvVarsPresenter` and `data/env_vars.txt`. To finish later: read the whole page `env-vars` (the first reading stopped in the C's), whether a change applies to a running session, and the Windows path of the managed settings file.
- Left for P1.7 from P1.2: the user adds a file to the watched list (`WatchedFiles.set_watched`), and the
  tab *Security* approves or restricts (`SecurityPresenter.approve` / `restrict`).
- `ProvidersPresenter` (the Preferences page: list, add, edit, delete, key saved / removed / shown),
  the Agent dialog presenter (provider list and models that depend on it), `SecurityPresenter`
  (trusted flag, list of watched files, accept a change, restrict), the approval and alert flow when
  a workspace opens (in `workspace_presenter.py`: ask once for a workspace used before, a dialog for a
  folder never seen, an announcement of the state), `EnvVarsPresenter` and the data file
  `src/wxclaude/data/env_vars.txt` (help text of each variable, outside the code like `tools.txt`).
- To do first for `env_vars.txt`: read the meaning of each variable in the official page
  `env-vars` (the earlier reading went through a summarizer) and note which ones the project files
  cannot set.
- **Wire the provider (left from P1.5)**: `RunPresenter` builds `RunRequest.provider` =
  `ProviderLaunch(store.get(agent.provider), store.key(id) if needed, settings.scrub_credentials)`
  and shows a `KeyVaultError` / `ProviderError` as an error before anything is started. The notice of
  the auto mode on stderr (`claude-cli.md`) is not filtered out of the details of a failure: its exact
  text is not known (only `[claude-code:unrecognized_model]` is).
- Done when: presenter tests for each flow, including the approval of a workspace used before, a
  change detected at opening, and the refusal to write over an external change.

**P1.7 Views and translations** (`ui/`).
- **Remove the button *Ask me later*** of the approval dialog once the tab *Security* exists (decided):
  Escape then means *Keep restricted*, `ApprovalChoice` loses the "no answer", and `approval_asked` is
  always set after the offer.
- Preferences: the page *Providers* and the check box of the scrub (page *Claude*); Workspace
  settings: the tabs *Environment variables* and *Security* (split the dialog by tab, as the
  Preferences are split by page, before adding to it); the dialogs of approval and of alert; the
  provider list in the Agent dialog; an announcement category for security.
- The French catalog, the accessible names, the initial focus, the entries of `focus.md`.
- Done when: the UI tests pass (real windows, fake `claude`), and the checklist for NVDA and JAWS is
  written in `roadmap.md` (password field and *Show the key*, the state announcements, the read-only
  text of the Security tab, the lists with their lines written out).

**P1.8 Close part 1.** Docs moved as described above, `CHANGELOG.md`, full checks, size warnings
reported, a commit proposed. The roadmap says what is left (parts 2 and 3).

Suggested commits: after P1.3 (restricted launch, useful alone), after P1.5, after P1.8.

## Part 2: a remote provider (DeepSeek)

Decisions to take with the user at the start: where the test key lives (a file outside the project,
deleted afterwards, or typed in the new Providers page); how the Claude-only parts (gauges, sign in,
cost) are shown for another provider.

**P2.0 Preparation.** The user opens the account, adds a small credit and creates a key dedicated to
this work. Read again the current page of DeepSeek on the Anthropic API (names of the models,
`deepseek-flash[1m]`, the variables it recommends): the page changes. Create the provider
(`https://api.deepseek.com/anthropic`). Measures use a work folder and a temporary
`CLAUDE_CONFIG_DIR`.

**P2.1 First contact.** One message through WxClaude, cheapest model and shortest prompt. Look at the
stream: the model named in `system/init`, `result`, `modelUsage` and `canonicalModel`, the stderr
lines, what a wrong key (401) and an empty balance look like. Record in `claude-cli.md`.

**P2.2 Parameters.** `--effort` accepted or not (settles `send_effort`); the `thinking` the CLI
sends; `ANTHROPIC_AUTH_TOKEN` versus `ANTHROPIC_API_KEY` (which header the server wants); the names of
the models and the aliases. Settle the defaults of a DeepSeek provider.

**P2.3 Tools and permissions.** `Read`, `Edit`, `Bash` in a dummy folder; both permission channels
(stdio, hook), the mode Plan, a structured question; the `WebSearch` tool (the documentation warns of
extra requests). Note what does not work.

**P2.4 Switching.** In one conversation: Claude (haiku, low) then DeepSeek then Claude again. Does the
provider accept the history (signed thinking blocks, context size)? Is the cache lost as expected?
If it fails, build the fall-back (offer a branch). Decide what is announced when the provider
changes.

**P2.5 Display for another provider.** After the decisions: costs, statistics (`cost_state.py`,
`workspace_stats.py`: families and prices are Claude's), gauges, the name of the model shown, which
provider answered each message, the errors of the provider (401, balance, 429) announced and shown in
a dialog like the other errors, the Claude-only commands greyed with their reason.

**P2.6 Security with the real provider.** The scrub with the real key shape; a booby-trapped dummy
folder with the DeepSeek provider (the URL is the provider's, not the project's); what is sent to
Anthropic when the base URL is another one, if it can be seen; with the user's consent only, whether
the subscription token goes to a URL set by a project file in a trusted folder.

**P2.7 Close part 2.** Manual run in the application, the checklist for NVDA and JAWS, docs and
`CHANGELOG.md`, the test files and the key deleted, a commit proposed.

## Part 3: a local provider (LM Studio or another)

**P3.0 Preparation.** The user installs the server, loads a model that handles tools and has a
large enough context, and starts the server. Find out whether it speaks the Anthropic API itself or
only the OpenAI one; in the second case a gateway (LiteLLM, claude-code-router) stands in front, and
the provider points at the gateway. Note the URL and the model names.

**P3.1 A provider without a key.** `key_source = none`: the key field is hidden or greyed with its
reason, a placeholder token is given to the CLI. Tests and views adapted.

**P3.2 Measures.** Time to the first token and CLI time-outs (`API_TIMEOUT_MS`), the window of context
(`CLAUDE_CODE_MAX_CONTEXT_TOKENS`, the compaction window), whether the model calls tools, `thinking`
and `--effort` accepted or not, the stream, the error when the model is not loaded or the server not
started (what the user sees).

**P3.3 Adapt.** *Decided and done (2026-11-11):* not a free list of variables (a free name could redefine the
address or the key) but a **closed list** per provider, `core/config/provider_variables.py`: `API_TIMEOUT_MS`,
`CLAUDE_CODE_MAX_CONTEXT_TOKENS`, `CLAUDE_CODE_AUTO_COMPACT_WINDOW` and `CLAUDE_CODE_MAX_OUTPUT_TOKENS`, in the
`env` of the provider, given in the inline `--settings` (measured: they reach the process, also with
`--setting-sources user`, and `API_TIMEOUT_MS` is used for the calls to the server; `claude-cli.md`). The form
has a list box *Variable* (the four models and these variables) and a field *Value*. What depends on the folder
(`BASH_MAX_OUTPUT_LENGTH`, the reading of a file) stays in the tab *Environment variables* of the Workspace
settings. DeepSeek and Ollama are defined at the first start. *Left:* the message when the server cannot be
reached.

**P3.4 Security with a local server.** The scrub and the restricted mode behave as with the remote one;
note that nothing leaves the machine, and say it in the Providers page.

**P3.5 Close part 3.** Docs, `CHANGELOG.md`, the checklist for the screen readers, the test files
deleted, a commit proposed. Then the roadmap goes on with its other milestones.
