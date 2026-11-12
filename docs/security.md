# Security: trusted folders and the user's data

**Status: built (part 1 of `plan-providers.md`), tested with the real CLI against a fake server, not
yet with a real provider.** The user interface is in `interface.md` ("Trusted folders", "Workspace
settings"), the files in `settings.md`, the modules in `architecture.md` (`core/security/`). The facts
come from runs of the real CLI against a fake server (`claude-cli.md`, "Folders never trusted and credentials" and
"Measured: restricted run, scrub and key helper") and from the official documentation. What is still
open is in `open-questions.md`.

## The aim and its limits

WxClaude does no more than Claude Code or VS Code do about the trust of a folder: it **tells the user**
of a sensitive change and the user **alone decides**. The responsibility is the user's, and the
Security tab says so.

It protects against what a cloned or copied project can do through its configuration files. It does
**not** protect against a prompt injection written in the code or the texts of the project, against a
folder that is already malicious when the user approves it, against a change made between two checks
(see "When it is checked"), or against a program running under the user's account.

## What the CLI does in a folder never trusted (measured)

`claude -p` never shows the trust dialog. In a folder that was never trusted it still:

- runs the **hooks** of the project's settings files (a command);
- applies the project's **`env`**, including `ANTHROPIC_BASE_URL`: the request went to the URL of the
  project, with the token of the process in the `Authorization` header;
- starts the command of each server of the project's **`.mcp.json`**;
- loads the `CLAUDE.md`, the commands and the agents of the project.

It does not apply the project's `allow` rules. And the tools of Claude (`Bash`, `PowerShell`) see the
credentials of the environment of the CLI, unless they are scrubbed.

## Restricted mode

A folder that is not trusted is run in **restricted mode**, with three elements:

1. `--setting-sources user`: neither the settings files nor the `.mcp.json` of the project are read.
   No hook, `env` or server of the project runs (measured). The `CLAUDE.md`, the commands and the
   agents of the project are not loaded either, which the user is told.
2. The **`deny` and `ask` rules** of the two project files are still applied: WxClaude reads them (it
   already does for the Tools tab) and gives them in the inline JSON of `--settings`, with what the
   launch already puts there (measured: they apply). They only restrict, which is why the CLI itself
   applies them before trust. The project's `allow` rules are left out; the Tools tab says so. A file
   that does not exist is read as empty.
3. The **permission mode is `manual`** for the message (the agent of the conversation is not changed),
   unless the agent is already in `plan` or `dontAsk`, which let Claude read but not act and are kept
   (forcing `manual` there would give Claude more power than the user chose). `acceptEdits` and `auto`
   become `manual`. It limits what Claude does without asking; it does not replace the first element,
   because hooks, `env` and servers run in the CLI before any permission question. Reading inside the
   workspace needs no question in these modes, which is why the `deny` rules are still given, and why
   the user can have the project examined by Claude (reading only) before deciding to approve it.

The provider of the agent is kept in restricted mode (its URL is given by `--settings`).

## Trusting a folder

The workspace settings hold a check box **Trusted folder**, off for a folder WxClaude has never seen.

- A **folder never seen** and a **workspace used before this feature** meet the same dialog once the
  window shows (the sentence says which it is). It proposes to approve the folder, lists the watched
  files it holds and says where to do it later (*Workspace settings*, tab *Security*). The buttons are
  *Approve the folder* and *Keep restricted*, which is the default one. The question is asked once;
  until the user approves, the folder runs in restricted mode and is announced as such when it opens.
- No trust is inherited from a parent folder.
- The state is WxClaude's own (`workspaces/<hash>.json`, key `trusted`); WxClaude never writes
  `~/.claude.json`.
- When a workspace is opened, its state is said without moving the focus ("folder not trusted,
  restricted mode", or "a watched file changed").

## Watched files

The Security tab lists the files that can change what the CLI does, each with a check box *Watch*.
Only files inside the workspace. The default list is `.claude/settings.json`,
`.claude/settings.local.json`, `.mcp.json` and the files of `.claude/agents`, `.claude/skills` and
`.claude/commands` (so that a file added or removed is seen too). `CLAUDE.md` is not in it. The user
can add files. WxClaude does not look for the scripts that a hook calls: it would be intrusive,
imperfect, and it would give a feeling of safety it cannot back.

For every file of the list, watched or not, WxClaude keeps:

- a **SHA-256** of the file, in `workspaces/<hash>.json`;
- a **copy of the approved content**, a `.bak` file in the folder `workspaces/<hash>.watch/`, to show
  what changed. In a JSON file, the value of a key whose name looks like a credential (`env` entries,
  `headers`) is replaced in the copy by its hash, so that a secret does not exist twice, and a text that
  is an URL keeps only its scheme, host and port (what follows can hold a secret in a form nobody can
  list: a token in a path, a user that is a token); a change of such a value is shown as another hash,
  without the content. A `.json` file that cannot be parsed has no copy.

Both stay in WxClaude's data, never in the repository (a project could rewrite them). A file that
did not exist when the folder was approved has no copy: its appearing later is a change.

**One mechanism writes these files for the whole application.** Whichever dialog changes one (Tools,
Environment variables), it first compares the hash (a file changed from outside is reported before
WxClaude writes over it), writes, then records the new hash and copy. No change made by WxClaude gives
a false alert.

## When it is checked

When a workspace is opened, and when a dialog that edits these files is opened. **Not before each
message**: the interactive CLI and VS Code do not either, and the user accepts the limit. `claude -p`
does read the files at each message, and Claude can edit them during one.

## The alert

A change in an **approved** folder is shown in a dialog: the list of the changed files and, under it, the
differences of the selected one with the approved copy (a file added shows as added lines). The choice
is the user's alone: **accept the changes** (new hash and copy), **restrict the folder**, or close the
dialog, which decides nothing: the change is announced and asked again at the next check. A restricted
folder is not alerted: the CLI ignores its files anyway, and the approval takes the files as they are
then. The focus is not moved by an announcement; a dialog is used when a decision is needed.

## The tab "Security" of the workspace settings

The check box *Trusted folder*; the list of watched files with their check boxes and their state
(unchanged, changed, absent, added); a read-only text field that explains the restricted mode, what
is lost in it and the risks (the Tab key reaches it, a screen reader reads it). The tab *Environment
variables* sits next to *Tools* and *Security*.

## The tab "Environment variables" (security part)

It lists the variables of the `env` key of the target file with a help text for each. A variable that
looks like a credential (name with KEY, TOKEN, SECRET, PASSWORD...) or that redirects the traffic (base
URL, proxy, certificates) is marked **sensitive** in the text of its line (not by colour only). Writing
one in the versioned file (*Settings*) rather than *SettingsLocal* gives a warning. The provider's own
variables are kept out of this list, as they are given at launch. Later: a way to alert the user of an
identified security point (to settle).

## The key

- **Where it is kept**: entered in WxClaude, encrypted with the Windows DPAPI (bound to the user's
  account) in `providers.json`. Never in clear, never in a file of the project. The field is a
  password field with a check box *Show the key*, opened by the button *Add a key* of the form of the
  provider; after saving, the key is never shown again, the list of the providers says *key saved* /
  *no key*, and the same button removes it. The field `key_source` leaves
  room for the Windows credential manager and for the name of an environment variable later.
- **Where it travels**: in the environment of the process of the CLI, never on its command line. Three
  places: the relay of the transmission *Relayed*, which holds the key and puts it in the requests it
  forwards to the provider, the dialog *Usage gauge*, which asks the credit of a provider with the gauge
  method chosen for it (key as a Bearer token), and the button *Check the data retrieved*, which asks the
  models and the credit with the two methods chosen: WxClaude itself sends a request to the host of the
  address of the provider, with the key in the headers, only when the user opens the gauge or presses
  the button (`providers.md`). A method gives paths only, never addresses (`provider_methods.py`: the
  base class puts them after the scheme and host the user typed; a test checks every registered
  method), and redirects are not followed, so the key never goes to another host than the one typed,
  and no message shows it.
- **The tools of Claude**: the user chooses (list *API key transmission* of the page Providers). *Masked*,
  the default, is the scrub (`CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1`): the CLI keeps the key for its own
  calls and the commands of Claude see it empty (measured with `Bash` and `PowerShell`). The scrub is
  all or nothing and also removes other credentials a command may need (`NPM_TOKEN`, AWS keys,
  a `DATABASE_URL` with a password); `GITHUB_TOKEN`, `GH_TOKEN` and the proxy variables stay, and
  credentials kept in files or stores (`~/.aws`, `~/.npmrc`, `~/.ssh`) are not touched. The CLI then forces
  the manual permission mode. *Shared* leaves the key readable by the commands of Claude, with every mode
  working; the page says it in the explanation under the list.
- **The relay** (*Relayed*): the key stays in WxClaude and the CLI is given a throw-away token and the
  address of a relay on `127.0.0.1` (`providers.md`, "The relay"). The commands of Claude can then not
  read the key, and the permission modes work. The relay listens on the loopback address only (no
  alert of the firewall is expected, to be checked), starts when it is needed, stops after 10 minutes
  without a request and forgets its tokens, logs nothing and keeps nothing of the traffic. Its limit: a
  command that finds the token can use the provider through the relay while it runs.
- **To reduce the damage of a leak**: a key dedicated to WxClaude, with a limited credit.

## Left out, on purpose

Checking before each message; watching the scripts a hook calls; forbidding Claude to edit the watched
files (an `Edit` deny rule given by `--settings` is easy but covers `Edit`, `Write` and the redirections
of `Bash`, not `sed -i` or a script, and `.claude` is already a protected path of the CLI); trust
inherited from a parent folder; `--bare` and `disableAllHooks` (they also remove what WxClaude needs:
skills, or the hook of the permission channel); `apiKeyHelper` for the key (it works, but the scrub is
simpler and the helper command could be run by an injection); the sandbox of the Bash tool (it does
not exist on native Windows); a summary of what the watched files would do (later); the managed
settings of an organization (not read).

## Why these choices

| Choice | Reason |
|---|---|
| Inform, the user decides | The user's rule: no more than Claude Code or VS Code do. |
| Restricted mode by `--setting-sources user` | Measured: it stops the hook, the `env` and the `.mcp.json` of a project. The alternatives (`--bare`, `disableAllHooks`) also remove what WxClaude uses. |
| `deny` and `ask` kept, `allow` dropped | A rule that restricts cannot grant anything, and the CLI does the same before trust. |
| `manual` forced | Cheap and in line with VS Code's restricted mode; not enough alone (measured: hooks run before any permission). |
| State kept by WxClaude, files hashed | Nothing of the repository can be trusted to hold its own approval. |
| Copy with masked values | A secret in a watched file must not exist a second time in WxClaude's data. |
| Check at opening only | Same as VS Code and the interactive CLI. |
| DPAPI for the key | Protects against a copied disk, a backup or another user; it cannot protect against a program running as the user, which no local scheme does. |
| Scrub rather than `apiKeyHelper` | Measured: both keep the key out of the tools' environment; the scrub needs no command of ours. |
