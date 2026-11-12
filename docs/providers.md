# AI providers

**Status: built (part 1 of `plan-providers.md`); tried with a local Ollama server (see "Measured with a
local server"), part 2 (a remote server) not done.**
The screens are in `interface.md` (Preferences > Providers, the Agent), the files in `settings.md`
(`providers.json`), the modules in `architecture.md` (`core/config/providers.py`,
`core/claude/launch.py`, `core/security/vault.py`). The facts below come from runs of the real CLI against a fake server (`claude-cli.md`, "Other
providers" and the three sections after it) and from the official documentation. What is still
open is in `open-questions.md`. The protection of the key and of the user's data is in
`security.md`.

## Why and what

The CLI can talk to any server that speaks the Anthropic API (a local server such as LM Studio or
Ollama, a remote service such as DeepSeek, or Claude itself through Bedrock or Vertex). WxClaude lets
the user choose, for a conversation or for one message, which provider answers.

**Provider** (French: *fournisseur*). The words that were rejected:
- *profile*: a provider is another source of models, possibly with other models, not a set of
  preferences;
- *agent*: already means a model, an effort and a permission mode (`interface.md`, "Agents");
- *model*: already names `haiku`, `sonnet`...;
- *connection*: collides with *Sign in to Claude…*.

## What a provider is

The built-in provider **Claude** (the subscription, or whatever the CLI is already configured for)
adds nothing to the launch of the CLI: it is today's behaviour, and it is the default. It cannot be
changed or deleted. The others are defined by the user, once for the application (Preferences, page
*Providers*), never per workspace:

| Field | Meaning |
|---|---|
| `id` | Stable identifier kept in the agents (`claude` is the built-in one). |
| `name` | Shown in the lists. |
| `base_url` | Endpoint that speaks the Anthropic API (for example `https://api.deepseek.com/anthropic` or `http://127.0.0.1:1234`). |
| `key_source` | Where the key comes from. `stored` (the key is kept encrypted by WxClaude) is the only one built for now. `credential_manager` and `environment` (the name of a variable) are left possible; `none` is for a local server that needs no key (a placeholder is then given to the CLI). |
| `name` | At most 15 characters. |
| `tiers` | Four model names, each at most 64 characters (an identifier sent to the server, so never cut; the field stops there), from the smallest to the largest (small, medium, large, largest), sent as they are to the server (the CLI accepts any name). Same ranks as the models of Claude. An empty one takes the weakest model given, so none is empty; one name is enough. They give the models offered in the Agent dialog (each once) and the aliases: the first three answer to `haiku`, `sonnet` and `opus` (the CLI variables `ANTHROPIC_DEFAULT_*_MODEL`); the fourth has no alias (no variable is known for `fable`). |
| `send_effort` | Whether `--effort` is passed. On by default; a server that refuses it turns it off. |
| `env` | The variables of the CLI this provider sets, from a **closed list** (`core/config/provider_variables.py`): `API_TIMEOUT_MS` (how long the CLI waits for the server, in milliseconds), `CLAUDE_CODE_MAX_CONTEXT_TOKENS` (the size of the context window the CLI assumes), `CLAUDE_CODE_AUTO_COMPACT_WINDOW` (how full the context gets before it is compacted) and `CLAUDE_CODE_MAX_OUTPUT_TOKENS` (the most tokens of an answer). They describe the server and its model; what depends on the folder (`BASH_MAX_OUTPUT_LENGTH`, `CLAUDE_CODE_FILE_READ_MAX_OUTPUT_TOKENS`) is set in the workspace settings, tab *Environment variables*. Whole numbers above zero; an empty value means not set. They go in the inline `--settings` with the address and the aliases, so they apply only to this provider and also in a restricted folder (the files of the project are not read there). A name outside the list is never sent, so a provider cannot redefine its address or its key. A slow local server needs a long `API_TIMEOUT_MS`; Ollama needs a context of 64K or more (see "Measured with a local server"). |
| `models_method`, `credit_method` | How to ask the server for its models and for its credit ("The data of a server" below). |

A user who has no `providers.json` yet starts with **DeepSeek** and **Ollama** already defined
(`settings.md`, "Providers"): the model names are the ones the two servers gave when they were tried,
the user changes them in the form.

They live in `providers.json`, next to `settings.json`, written like the other files
(`jsonstore.py`: atomic write, `.bak`, damaged file set aside). The key is kept in that file as an
encrypted block (`security.md`, "The key"), never in `settings.json`: the settings can then be
copied, shown or backed up without a key in them.

## Where a provider is chosen

`Agent` gets a fourth field, `provider` (the id; `claude` by default), next to the model, the effort
and the permission mode. An agent is always complete, so the rule is the same as for the others. It
is therefore chosen at the three levels that already exist:

- `default_agent` (Preferences): the provider of a new conversation;
- the main agent of the conversation (Agent dialog, `Ctrl+Shift+A`);
- `alternative_agent`: a message sent with Shift+Enter can go to another provider.

In the Agent dialog the list *Provider* comes first and the list of models depends on it: changing the
provider takes the first model of the new provider, unless the current model is also one of its
models. Everything else about an agent is unchanged.

**Switching in a conversation keeps one context.** The conversation stays one session of the CLI
(one file), resumed with `--resume` whatever the provider, so the new provider receives the whole
history. Changing the provider loses the prompt cache, like changing the model. Whether a provider
accepts a history written by another is not known (thinking blocks signed by Claude, a smaller
context): it is measured with a real server (`plan-providers.md`, part 2). If it fails, the fall-back
is a branch (`--fork-session`, `interface.md`, "Branch and delete"), which copies the history into a
new session.

## How the CLI is launched

For a provider other than Claude, for every message:

- **Environment of the process** (`env=` of `Popen`, never on the command line): the key as
  `ANTHROPIC_AUTH_TOKEN`; `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1` when the *API key transmission* is *Masked*
  (the default); and the
  variables that turn off what is sent to Anthropic (`DISABLE_TELEMETRY`, `DISABLE_ERROR_REPORTING`,
  `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`). The `ANTHROPIC_*` and `CLAUDE_CODE_USE_*` variables that
  WxClaude itself inherited are removed first, so that two providers never mix.
- **Inline JSON of `--settings`**: an `env` with `ANTHROPIC_BASE_URL` and the aliases of the models.
  It is merged with what the permission channel already puts in `--settings` (the CLI is given one
  `--settings`).
- `--model` with the model name, and `--effort` only if `send_effort` is on.

For Claude nothing is added. The transmission applies to the other providers only (Claude's own
credentials are not in the environment).

## How the key reaches the CLI

The user chooses it in the page Providers (list *API key transmission*, with a read-only explanation):

- **Masked** (default): the scrub is on. The CLI keeps the key for its own calls and the commands that
  Claude runs (`Bash`, `PowerShell`) see it empty. But the CLI **forces the permission mode to manual**
  (`Permission mode forced to default`): Plan, Accept edits, Auto and Don't ask are not applied (measured
  with DeepSeek, `claude-cli.md`).
- **Shared**: the key stays in the environment of the CLI. Every permission mode works, but the commands
  that Claude runs can read the key (measured: `Bash` saw it), and an instruction hidden in a file or a
  web page could make Claude reveal it. A key made for WxClaude with a limited credit reduces the damage.
- **Relayed**: the key stays in WxClaude (see "The relay" below). The CLI is given a throw-away token and
  the address of a relay on this computer; the scrub is off, so every permission mode works, and the
  commands that Claude runs find only the token (measured: `Bash` saw 43 characters, the token, not the
  35 of the key).

The choice is kept as the setting `key_transmission` (`masked`, `shared`, `relayed`); a file from before
it, with the yes or no `scrub_credentials`, gives `masked` or `shared`. A provider that needs no key has
no secret to hide: the scrub and the relay are not used for it, so its modes are left alone. The
sandbox of Claude Code does not help on native Windows (`claude-cli.md`).

## The relay

`core/security/key_relay.py`, used for the transmission *Relayed*:

- **What it is**: a small HTTP server of the standard library (`ThreadingHTTPServer`, `http.client`) in
  a thread of WxClaude. It listens on `127.0.0.1` only, on a port the system chooses.
- **What the CLI gets**: `ANTHROPIC_BASE_URL=http://127.0.0.1:<port>` (inline `--settings`) and
  `ANTHROPIC_AUTH_TOKEN=<token>` (environment). The token is random (43 characters), one per provider
  for as long as the relay runs.
- **What it does with a request**: it checks the token (`Authorization: Bearer` or `x-api-key`, compared
  in constant time; else 401), keeps only the paths under `/v1/` (else 404), reads the body (at most
  64 MB), forwards it to the address of the provider followed by the path with the real key as
  `Authorization: Bearer` (the other headers are kept, those of one connection and the credentials are
  not), and copies the answer back piece by piece as it arrives, so that a stream of events is not held
  back. A provider that cannot be reached gives a 502 in the shape of the API of Anthropic. Redirections
  are not followed by the provider side (`http.client` does not).
- **When it runs**: it starts when a message to a provider that needs a key is prepared, and only then
  (never for Claude, never with *Masked* or *Shared*, never for a provider without a key). It stops when
  WxClaude closes and after 10 minutes without a request (checked every 30 seconds; a request being
  answered keeps it alive), and the tokens are forgotten with it: the next message starts it again with
  new tokens. So a provider can have several tokens in a WxClaude session, but not one per message.
- **Two settings, in `settings.json` only (no interface)**, read when WxClaude starts:
  `relay_idle_minutes` (the 10 minutes above, 1 to 120) and `relay_timeout_seconds` (the wait for the
  provider, 600 by default, 30 to 3600: a model can think for a long time). A value out of its range or
  of the wrong kind is ignored. The address (`127.0.0.1`) and the port cannot be changed.
- **What it keeps**: nothing of the traffic is logged or stored. The key is in memory only, in the
  route of the token. The relay sees the prompts and the answers in clear, as WxClaude does.
- **Speed**: the relay adds nothing measurable to a request (measured against the same request sent
  straight to DeepSeek). One thing mattered: the answer is sent as the headers then the first piece, two
  small sends in a row, and with the Nagle algorithm Windows delayed the second by about 0.2 s for each
  request of the CLI (a message with a tool took 3.6 s instead of 3.1 s); the handler turns it off
  (`disable_nagle_algorithm`). Keeping the connections to the provider open for the next request was
  tried and gave nothing (a new TLS connection costs about 0.04 s), so each request opens its own.
- **Errors**: it does not translate them; they are in the shape of the API and are shown by the CLI.
- **Not covered**: a command of Claude that finds the token can use the provider through the relay
  while WxClaude runs (and so spend its credit); it cannot read the key.

## The data of a server: the methods

A provider stays plain data. What WxClaude knows about how to question a service is in classes of
`core/config/provider_methods.py`, and the user picks one for each provider in two lists at the bottom
of its form (after *Send the effort*):

| List | Choices today | Stored as |
|---|---|---|
| *Models retrieval* | *No method*, *V1* | `models_method`: `none`, `v1` (a new provider and a file from before the lists: `v1`) |
| *Gauge retrieval* | *No method*, *DeepSeek* | `credit_method`: `none`, `deepseek` (a new provider and a file from before the lists: `none`) |

A value that is not known reads as *No method*. WxClaude does not choose for the user: a provider that
was added before the lists keeps its models method `v1` and has no gauge until the user picks one.

**One base class per family.** `ProviderMethod` holds what the two families share: the call (the
`GET`, 15 s at most, no redirect followed, the answer read up to 1 MB), the key as a bearer token, and
the messages for the failures (key refused, 404, redirection, server unreachable, an answer that is not
JSON). `ModelsMethod` and `CreditMethod` add what is of their family; a method is a subclass that gives
its `id`, its `label` (the text of the list), its `paths(base_url)` and the reading of the answer
(`parse`). The classes are listed in `MODELS_METHODS` and `CREDIT_METHODS` (explicit registries, no
automatic discovery): to add a method, write the subclass, add it to its registry, add its label to the
catalog. A test goes through every registered method and checks the rule of the key below.

**The key goes to the host the user typed, and nowhere else.** A method gives paths (`/v1/models`,
`/user/balance`), never addresses: the base class puts them after the scheme and host of the address
of the provider. So a method, whatever it is, cannot send the key to another host, and the credit
method of DeepSeek, chosen for a provider whose address is another one, asks that address.

**Models, `V1`.** `GET <base_url>/v1/models` (`/models` if the address ends in `/v1`), the names in
`data[].id`; a 404 is followed by the root of the same host (`/v1/models`, then `/models`: DeepSeek keeps
its list at the root while the Anthropic API sits under `/anthropic`). It is the format of the API of
Anthropic and of the OpenAI one of the local servers (LM Studio, Ollama). It helps to fill the four ranks
of the form: the user types the names, nothing is filled by itself.

**Credit, `DeepSeek`.** `GET /user/balance` on the host of the address (key as a Bearer token); answer
`balance_infos` with `currency`, `total_balance`, `granted_balance` and `topped_up_balance`, and
`is_available`; measured 2026-11-10. More methods, the most generic possible, are added as they are
tried with real services.

**Checking the choice.** The button *Check the data retrieved* of the form, right under the two lists
(greyed while a key is needed and missing, or when both lists say *No method*), asks the server with
the two methods chosen, away from the window thread (once at a time), and shows what they give in one
read-only text: the models, one per line, then a blank line and the credit. A failure of one method
is a line of the text (`Models not available. The server refused the key (error 401).`) and the other
still answers. It does not prove that the CLI works with the server (effort, thinking and tools). The key
is removed from every message.

**The gauge.** The dialog *Usage gauge* (Tools menu) shows, under the gauges of Claude, the credit of
each provider that has a key saved and a gauge method other than *No method*, one provider after the
other with a blank line between, asked away from the window thread when the dialog opens. A provider
with no method or no key has no line. A failure is a line of the dialog, never an error box, and never
holds the key.

## What stays Claude's

Signing in (*Tools > Sign in to Claude…*), the state of Claude Code, the gauges read with `/usage` and
the cost shown by the usage dialog describe the subscription. With another provider they must not
suggest otherwise: the CLI computes its cost from its own price list, and for a model it does not know
it still gives a figure (`costBasis` is `unknown`, `claude-cli.md`). How each one is shown for another
provider is not decided yet (`open-questions.md`).

## Measured with a local server

A first test with **Ollama** (`http://localhost:11434`, provider without a key, models method `V1`,
model `qwen3:4b`, Q4_K_M, 100% CPU on a machine with 15 GB of RAM and no discrete graphics card) is
conclusive: the connection works from WxClaude through the CLI to the model, the stream is shown, the
effort is accepted and the model emits a tool call. What it showed:

- **The context window decides.** Ollama's default context was 4096 (`ollama ps`, column `CONTEXT`),
  much smaller than the prompt of the CLI: the model never saw the question and answered with a
  sentence about a missing user query, the same for every message. With 64K the question was
  answered. It is set in the settings of Ollama or with `OLLAMA_CONTEXT_LENGTH` (Ollama restarted
  afterwards); `ollama show` gives the maximum of the model, not the value in use, so `ollama ps` while
  the model is loaded is the check. Ollama's own documentation advises 64K or more for Claude Code.
- **A 4B model is weak with tools**: asked how many days a week has, it called `WebFetch`. Keep the
  permission mode manual with such a model.
- **Not measured yet**: time to the first token, the memory used at 64K, several messages in a row,
  and the errors (server stopped, model not loaded): the rest of part 3 of `plan-providers.md`.

## Not in this version

A provider per workspace (the user decided against it); several keys for one provider; the models
filled by themselves from the server (the user types the four names; an aggregator is added several
times under different names); a method chosen by itself from the address; the credential manager and the environment variable as sources of
the key (the field `key_source` leaves room); Bedrock and Vertex as providers.

## Why these choices

| Choice | Reason |
|---|---|
| A *provider* field of the agent | The three levels (default, conversation, alternative) already exist and an agent is already always complete; switching is one more list in a dialog the user knows. |
| Defined in the Preferences, not per workspace | The user's decision; the key then never depends on a project folder. |
| URL by `--settings`, key by the environment | Measured: `--settings` beats the project files while the environment of the process does not (a project file can redirect the CLI and the token of the process goes to that URL); the variables are merged key by key, so the key can stay in the environment. A key on the command line is visible to other programs. |
| Credentials scrubbed from the tools | Measured: `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1` keeps the key for the CLI while `Bash` and `PowerShell` see it empty. Simpler than `apiKeyHelper`, which also works but needs a command of ours that anyone running as the user can call. |
| Telemetry off for other providers | The user's decision: nothing is sent to Anthropic when the user chose another provider. What the CLI sends in that case is not known. |
| One shared context when switching | One session file, the simplest; it is tested before it is relied on, and a branch is the fall-back. |
| Free model names | Measured: the CLI sends any name as it is. |
| `--effort` optional | The CLI sends it as `output_config.effort`; a server may reject it. |
| `providers.json` apart from `settings.json` | Keys never travel with the settings. |
