# Open questions and improvements

The other files of `docs/` describe what is true and decided. Everything that is still to decide,
to verify or to improve lives here, and nowhere else. When an item is settled, move the result to
the file it belongs to and delete it from this one.

## To decide

- **Help page.** Built (see `interface.md`). To check: the page with NVDA and JAWS in the browser,
  the exact names of the Preferences pages in the French text, and the Claude Code install and login
  steps when they change.
- **The `&` of the labels in the Preferences.** The access keys (`&Language`, `&Path of claude-p`,
  ...) may hinder the reading of the labels with a screen reader. To check, and if so, remove them
  from the Preferences (the accessible name already comes without the `&`, see `core/labels.py`).

## To verify

- **Plans.** *Tools > Plan…* finds the plans as the `Write` calls of the session file to
  `<config>/plans/`; only that case was seen (haiku, two runs). The folder of the plans may be
  configurable (not checked), and a plan may also be written by another tool. With the stdio
  protocol the `ExitPlanMode` request holds the text of the plan (`input.plan`) and the file where it
  is saved (`input.planFilePath`): the request is shown as a plan (see `interface.md`, Permissions;
  tried with haiku, a refusal with an explanation is understood by Claude). Still to check: what Claude
  does after an approval (the `Write` of the plan, then the work) with a longer plan, and the dialog
  with NVDA and JAWS.
- **HTTP hook channel, not tested yet.** `updatedPermissions` (a rule for the session), `interrupt`,
  `decision.rule` (one documentation page), a waiting time above 10 minutes (the maximum accepted
  by the CLI), `tool_use_id` (the documentation lists it, the real POST has none).
- **Screen readers and the Preferences, Announcements tab.** The list of the announcement
  categories, the two sounds (WAV files in `wxclaude/sounds`, played with `winsound`) and the status
  bar left alone with *No announcement* are to be checked with NVDA and JAWS.
- **Screen readers and the Preferences, Claude tab.** The list *Interface type* and the spin
  control are to be checked with NVDA and JAWS.
- **The log and the error boxes** (*Help > Open the log folder*, the button *Copy the details* of the error
  boxes, `interface.md`): to check with NVDA and JAWS: the two buttons of the error box (*Copy the details*,
  *Close*, which has the focus) and their access keys, the announcement *Details copied*.
- **Remote control (`--remote`, `remote.md`).** Checked with the tests and with a Python client; still
  to try: a PowerShell client (the example of `remote.md`), the title *Remote enabled* read by NVDA and
  JAWS, and the rights of the pipe from another account of the computer (the documentation of Windows
  says it cannot write to it; not tested). Open: a request while a modal dialog is open (the client
  gets `timeout` after 5 seconds), and the pipe when WxClaude runs as administrator (another account
  could be refused).

- **The hidden window of the announcements.** It now lives under the panel, no longer under the
  status bar (the status bar read by the screen reader gave the last announcement, in the same
  launch every time, and not in another). To check with NVDA and JAWS: reading the status bar
  several times, over several launches, gives only the position, the step and the message; if a
  screen reader still adds an announcement, empty the name of the element after the notification.
- **UI Automation notifications and JAWS.** They reach NVDA and Narrator; test JAWS, with a focusable
  progress field as a fallback if they do not.
- **Reading the usage gauges with `/usage`** (built, `interface.md`). To check by hand: the wording
  of the text on other plans or when a gauge is at 0 % (no reset time?), a week gauge named
  differently, the status bar message with NVDA and JAWS (JAWS may read it by itself), and that a
  reading never takes the focus away from a send button (rule of `focus.md`). The status bar error
  of a failed answer is replaced by "Ready" at the next reading.
- **Title entry of a generated title**: the reader expects an `ai-title` entry with an `aiTitle`
  field; only `custom-title` / `customTitle` was seen in real files.
- **Effort in the session files**: only `low` and `medium` were seen. Are `xhigh` and `max` written
  the same way, and are `effort` and `perTurnEffort` always equal?
- **Settings files while `-p` runs.** The documentation says Claude Code watches its settings
  files and applies a change to a running session; check it for a `-p` process (a rule written by the
  Workspace settings during an answer).
- **A git-tracked `settings.local.json`.** The documentation says the CLI then treats its allow
  rules as coming from the repository and holds them until the folder is trusted; check what `-p`
  does, and if needed warn in the Workspace settings (detect with `git ls-files`).
- **Statistics of the workspace.** To check: (1) the files of a branch made in the interactive
  CLI with `/branch` (only `--fork-session` with `-p` was seen): the import tells a branch by the
  identifiers of the messages it shares with another session and by having no totals of its own
  among them; if `/branch` copies the `cost-state` entries, the copied history is counted twice in
  the first count; (2) the cost and the messages of a message are given to the model the CLI
  reports at the start (`system/init`), so the work of a subagent on another model is not
  separated (the import is exact, it reads the models of the totals); (3) an interrupted message is
  not counted at all (no `result`), nor the tokens it used; (4) the time of work of the import
  (`totalAPIDuration + totalToolDuration`) and of the new messages (`duration_ms` minus the waits)
  are two measures of the same thing: compare them on a real conversation.
- **Claude Code missing or not logged in.** Done: the start message and the status bar line for a missing
  program, and the same for a program that is not logged in (`interface.md`). Decided against (2026-11-12):
  greying the send buttons (the interface stays usable, the error comes with the message), a *Try again*
  button, and the address and steps of the installation in the message. To check: a login that expires
  during a session is only seen with the next message (the status bar is not read again by a timer); a
  conversation sent with another provider than the default one, while Claude is not logged in, is not
  warned about.
- **Signing in to Claude Code from WxClaude, what is left.** *Tools > Sign in to Claude…* exists
  for the subscription (`interface.md`, "Sign in"; the CLI needs no code, `claude-cli.md`). Not done:
  *Sign out* (`claude auth logout`); the other kinds of sign-in of `auth login`: `--sso` (the
  identity provider of an organization, Team or Enterprise offers; with `--email` to pre-fill the work
  address) and `--console` (Anthropic Console, API billing), the user being on a personal Pro account;
  a way in from an expired session (the error
  "Failed to authenticate: OAuth session expired…" stays in the conversation, the user opens the
  dialog). To check: `--email` together with `--claudeai` on the real sign-in page; the exit code of
  `auth login`; the question of the working folder that a user saw before the browser opened (not
  reproduced with the output redirected: if it comes back, the dialog has to show it).
- **Moving or renaming the folder of a workspace** (measured with the real CLI, haiku): no command of
  Claude Code does it; `/cd` exists in the interactive mode only and is refused with `-p` ("/cd isn't
  available in this environment"). `--resume <id>` finds a session by its identifier from any folder
  and keeps writing in the folder of sessions of the old path; `--continue` and the project memory
  (`memory` next to the sessions) follow the name of the folder of sessions under
  `~/.claude/projects`, so after a rename they only come back once that folder is renamed by hand
  (a new empty one made for the new path must be removed first). The `cwd` written in old transcripts
  stays; new lines carry the new path. WxClaude lists the conversations of a workspace by the `cwd` of
  the first lines of each folder (`claude_projects.list_sessions`), so after a rename it would not
  show them for the new path, and its own files (current conversation, agents, statistics) are named
  after a hash of the path. A "Rename the workspace" function would rename the folder, move the folder
  of sessions with its memory, migrate the files of WxClaude and fix that list. Not done; the user said
  to forget the files of WxClaude for now.

## Improvements not done yet

- **A thread that ends after the application.** `ui/worker.run_in_background` (the check of the login
  of Claude, the credit of the providers) hands its result over with `wx.CallAfter`, which fails with
  `No wx.App created yet` once the application is gone. The tests wait for these threads at the end of
  the session (`tests/ui/conftest.py`). In the application the same could happen if it is closed while
  one of them runs: the error would then be written to the log (level critical, `core/diagnostics.py`).
  Not seen in use, and harmless; the same pattern exists in `ui/run_view.py` and the remote control.

- **AI providers and trusted folders, what is left open.** Described in `providers.md` and
  `security.md`; part 1 of `plan-providers.md` is built, parts 2 and 3 need a real server. Open:
  - **The scrub forces the permission mode to manual.** Measured with DeepSeek (`claude-cli.md`,
    "tools and permission modes"): with `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1`, which is on by default for a
    provider, `plan`, `acceptEdits`, `auto` and `dontAsk` all become `default`; Plan mode even writes
    files (after a question). Without the scrub they are honoured. To decide: warn the user when
    `system/init` gives another mode than the one asked (and say why), and/or turn the scrub off by
    default (the key is then in the environment of the tools of Claude). The text of the check box does
    not say it yet. Tried and failed (2026-11-10): `--allowedTools Read`, and `allowedTools` or
    `permissions.allow` (Read, Glob, Grep) in the inline `--settings`: the mode stays forced. The
    variable is not in the official reference (only in bug reports of the CLI, one of which asks that it
    stops overriding the mode), so the behaviour may change. *Done:* a message that runs in another
    mode than the one sent is announced, with the reason when the transmission is *Masked*
    (`interface.md`). *Left:* whether to turn *Masked* off by default, and a sentence about it in the
    text of the choice (the explanation of *Masked* already says it). Seen on the way: `auto` is
    reported as `default` even with Claude (haiku, `claude-cli.md`), so that warning also fires for
    `auto`; why the CLI does not apply it (the account or the model) is not known.
  - **`apiKeyHelper` measured (2026-11-10, DeepSeek, CLI 2.1.286)**: with the helper in the inline
    `--settings` and no `ANTHROPIC_AUTH_TOKEN` in the environment, the CLI authenticates (the helper
    prints the key). *Without* the scrub the modes are honoured (`plan` gave `permissionMode` `plan` in
    `system/init` and wrote a plan) and `Bash` sees an empty `ANTHROPIC_AUTH_TOKEN` (`len=0`). *With* the
    scrub the mode is forced to default as before, so the helper gains nothing there. What stays: the
    command of the helper can be run by `Bash` (any process of the user can run it; not run in the
    test, true by construction). So it is a third way between *Masked* and *Shared*: modes work, the key
    is not in the environment, but it is one command away. Not built; a list entry *Helper* would do it.
  - **The relay, what is left to check** (built and tried with DeepSeek, `claude-cli.md`): whether the
    firewall of Windows or an antivirus reacts to the port on `127.0.0.1` (not seen so far); long
    answers and several requests at once (sub-agents) on a real session; the default of the list (still
    *Masked*; *Relayed* could become the default once it has been used for a while); `aiohttp` as a
    fall-back if the stream proves fragile. The idle time and the wait of the relay are settings of
    `settings.json` with no interface (an interface would be two number fields in the page Providers).
    The relay is in the process of WxClaude (a separate console executable was considered and left
    out for now).
  - **Other ways to give the key to the CLI**, from the documentation and bug reports read on 2026-11-10:
    (a) *Standard input*: nothing in `stream-json` carries a credential; not possible. (b) `apiKeyHelper`
    (official setting, a command the CLI runs to get the key; the order is `ANTHROPIC_AUTH_TOKEN`,
    `CLAUDE_CODE_OAUTH_TOKEN`, `apiKeyHelper`, the login, `ANTHROPIC_API_KEY`): the key is then not in
    the environment, but the command is one anyone running as the user, Claude's tools included, can
    call (already rejected in `providers.md`). (c) `CLAUDE_CODE_API_KEY_FILE_DESCRIPTOR` (found only in
    dumps of the source, undocumented): reads the key from an open file descriptor; Windows passing of a
    descriptor to the child and whether the tools inherit it are unknown. (d) **A local relay in
    WxClaude** (a token system; built, see "The relay" in `providers.md`): `ANTHROPIC_BASE_URL` points to `127.0.0.1:<port>`, the CLI gets a
    throw-away token, the proxy adds the real key and forwards to the provider. The real key never
    reaches the CLI, so the scrub (and its forced mode) is not needed (the sandbox of Claude Code, with
    its `sandbox.credentials` setting, is no way out on native Windows: measured, see `claude-cli.md`); a tool that finds the token can
    only use the proxy while WxClaude runs. Built with the standard library; what is left is below.
  - **Cost, statistics and gauges with another provider.** The CLI computes its cost from its own
    price list and gives a figure even for a model it does not know (`costBasis` `unknown`); the
    families of `workspace_stats.py` are Claude's; `/usage` is the subscription's. Not decided: what
    is shown (tokens only?), and which Claude-only parts are greyed (sign in, state of Claude Code,
    gauges).
  - **Which provider answered each message**: to show and to count, and where it is kept (the session
    file holds the model name the server returned).
  - **With a real server** (parts 2 and 3 of the plan). Settled with DeepSeek (`claude-cli.md`):
    `--effort` accepted, `ANTHROPIC_AUTH_TOKEN` works, the token wins over a claude.ai login, and a
    session can go Claude, DeepSeek, Claude. Still to measure: tools and permissions with a small model
    (P2.3), a long thinking block of Claude sent to DeepSeek, what the CLI sends to Anthropic when the
    base URL is another one, and everything for a local server (part 3).
  - **The four ranks and the aliases.** A provider has four models (small, medium, large, largest);
    the first three answer to `haiku`, `sonnet` and `opus`. To check with a real server that the CLI
    asks for these names by itself, and whether a variable redirects `fable` (none is known).
    The button *Check the data retrieved* shows the list a server offers (method *V1*, `providers.md`);
    to check with a real server (DeepSeek, LM Studio, Ollama) the path and the format, and that DeepSeek's
    list is found at the root of its host. Other methods, the most generic possible (models and gauge),
    are to be added as real services are tried.
  - **The variables of a provider.** The closed list (`API_TIMEOUT_MS`, `CLAUDE_CODE_MAX_CONTEXT_TOKENS`,
    `CLAUDE_CODE_AUTO_COMPACT_WINDOW`, `CLAUDE_CODE_MAX_OUTPUT_TOKENS`) is measured only as far as the process
    receiving them and `API_TIMEOUT_MS` being used (`claude-cli.md`). Not measured: the effect of the context,
    the compaction window and the output limit on what the CLI sends and when it compacts, with a real model.
    Others may join the list when a real need shows (one line in `provider_variables.py`).
  - **The focus after Alt+Tab** (`focus.md`, rule E). Built from the documentation of Windows and checked only
    with simulated events, not with a real Alt+Tab or a screen reader. If Windows has moved the focus before the
    window is told it is deactivated, nothing is remembered and nothing is restored; if losses of focus go on,
    follow the last focused control continuously instead of reading it at the deactivation.
  - **The subscription token and a project file.** Whether the token of a claude.ai sign-in is sent
    to a URL set by a project file in a trusted folder. Needs a real sign-in (the token would only
    go to `127.0.0.1`) and the user's consent.
  - **The `env` of the settings files**: the order between the two project files and the general
    file; `--settings` given as a file; whether a change applies to a running session; whether the
    scrub also removes the `env` an MCP server is configured with; the Windows path of the managed
    settings file (read only).
  - **Sensitive names**: the lists are in `core/security/sensitive.py` (settled for now: `DATABASE_URL`
    is not sensitive by its name, its value is masked as an URL); to review with real files.
  - **The list of environment variables** (`data/env_vars.txt`, 38 lines) was written from the part of
    the official page `env-vars` that could be read (it stops at `CLAUDE_CODE_NO_FLICKER`, and went
    through a summarizer): read the whole page, and note which variables the project files cannot set.
  - **Approval and the restricted folder**: the approval takes the watched files as they are; a summary of
    what they would do (hooks, servers, `env`) before approving is left out (see below).
  - **A key that cannot be decrypted** (another account): the page Providers says so when a message is
    sent; nothing offers to enter it again from that message.
  - **Alerting the user of a security point** beyond the cases of `security.md`: the announcement
    center for information, a dialog when a decision is needed, and a place where the points stay
    listed (the Security tab).
  - **In restricted mode** the `CLAUDE.md`, the commands and the agents of the project are not
    loaded (measured); no setting of the CLI was found that loads only `CLAUDE.md`.
  - **Left out, may come back**: a check before each message; a summary of what the watched files
    would do; forbidding Claude to edit the watched files; the credential manager and the
    environment variable as sources of the key.

- **Automatic checks still to write** (each one a test run by `pytest`, tried on a small tree or
  dialog made for the purpose and on the real code). In this order:
  1. Direction of the imports: nothing in `core/` imports `wx` or `wxclaude.ui` (read with `ast`).
  2. No circular dependency between modules (graph of the imports, search for a cycle).
  3. Accessible name: every control of every dialog has one (a name equal to the default name of
     wx, such as `text` or `listBox`, counts as none).
  4. Initial focus: every dialog has a control that holds it, and it is not the dialog itself.
  5. Access keys: unique inside a dialog (one page of a notebook at a time), in French and English.
  6. Translations: every text given to `_()` is in the catalog, no entry is unused, the compiled
     file is up to date.
  7. No concatenation inside `_()`: its argument is a text literal.
  8. Documents: every module of `core/` and `ui/` is named in `architecture.md`.
  9. Classes with too many attributes or methods: same method as the size test (an absolute
     limit that gives a warning at every run).

  Not checkable by a tool: whether a split makes sense, whether a data object holds only data
  (check 1 only keeps it from importing `wx`), and code duplicated between files (Pylint's
  `duplicate-code` could do it if it becomes a problem).
- **Template for a new Python project with an interface.** `working-rules.md` is the first generic
  document. To look at more closely: which sections of the other documents are generic (the four
  focus rules of `focus.md`, the plans of `roadmap.md`, `open-questions.md`, `architecture.md` and
  `settings.md` as empty templates), a folder of templates kept outside this project (for example
  `templates/python-ui/`, so that WxClaude does not depend on another project), and a test that
  checks the size of the source files.
- Details dialogs: the thinking and the token usage of one answer are kept by the model but not
  shown yet; the usage dialog cannot show the context window filled (`modelUsage.contextWindow`
  is in the `result` line).
- Task list: it is a snapshot when the dialog opens (no refresh while it is open), and the current
  task is not shown in the status bar yet.
- After a turn the view is rebuilt from the session file; the answer titles then show the effort
  written in the file, and none for a model that ignores it (haiku).
- *Always allow* in the permission question writes the exact rule the CLI proposes
  (`Bash(touch x)`); a wider rule is added by hand in the Workspace settings.
- The tools of the Workspace settings come from `data/tools.txt` and the files: the tools announced
  by the last run (the `tools` of the `init` line) are not added yet.
- The Workspace settings only edit the rules; other keys of the files (`env`, additional directories,
  instructions) are for later tabs.
- **Answer the stdio permission questions from a worker thread.** `ClaudeRunner.allow` and `deny`
  write to the stdin of the CLI from the window thread. The line is short and the CLI is waiting
  for it, but a full pipe (large `updatedInput`, CLI not reading) would freeze the window. A worker
  thread removes the risk; the `RunnerError` of `allow` and `deny` would then come back with
  `wx.CallAfter` instead of being raised on the spot. The hook channel does no input or output in
  the window thread: the window thread only hands the decision to the thread of the HTTP handler.
- **Structured questions of Claude** (`AskUserQuestion`): the dialog is written and tested with the fake
  `claude`, and the real CLI (stdio channel, `haiku`, `low`) was tried: a free text answer and a multiple
  choice joined with ", " came back to Claude as given (`Database: MariaDB (my own), Extras: Cache,
  Queue.`), and a refusal made Claude say the action was denied. Still to check with NVDA and JAWS (lists,
  check boxes, the message when a question is left unanswered).
- **Compaction of the conversation, what is left.** The live announcement is built (`interface.md`,
  "Compaction"; the stream carries `compact_boundary`, checked with `/compact`, `claude-cli.md`). Not
  done: a short line written by WxClaude in the conversation, where the hidden summary was, so that a
  user who reads the conversation later (or after F5) sees that it was compacted. The session file has
  the `compact_boundary` entry just before the summary (`compactMetadata`, in camel case), which the
  reader ignores. Not checked: an automatic compaction (a full context) in a real run; only `/compact`
  was.
- **The wording of the three new announcements** (retry, compaction, mode not applied) is a first
  proposal to read with NVDA and JAWS: length, and whether "you can interrupt" is wanted at each retry.
- **Spelling errors in the prompt.** A test (a red wavy underline put on a word of a rich text prompt
  with `SetStyle`, which Windows held as a wavy underline) was read with NVDA: the underline was
  displayed but not reported. The test item and the rich text prompt were removed. So the errors must
  be said another way, fed by a spell checker (next item). **Design wanted by the user**: a shortcut
  in the prompt opens a spelling dialog.
  - A list of check boxes: one line per misspelled word, with the correction proposed, all checked at
    first (the line says the word and the proposal, for example "wrold, world").
  - Tab goes to an editable drop-down list with the other choices for the selected line; the user can
    pick one or type a word of their own, and that becomes the correction of the line.
  - Enter corrects every checked line in the prompt; Esc changes nothing. Unchecked lines are left as
    they are.
  - To settle: the shortcut (configurable, like the others, in the Preferences list), the words
    to skip (code, paths, names), a dictionary of the user, and the language. The prompt stays a
    plain field, the dialog works on its text and gives the corrected text back (the caret is
    kept as near as it was).
- **Bold and italic shown as formatting.** The marks are removed from the conversation (item *Remove the
  Markdown formatting* of the Display submenu), but the words are not styled. `emphasis.py` could
  also give the places of the emphasis, to apply bold and italic with `SetStyle` (the view is a rich
  text field), again after every rebuild of the text, under an option of the Preferences. NVDA says
  such attributes only when "document formatting" is set for them, and it did not read the wavy
  underline of the spelling test (see below), so it is a visual gain only. To decide if wanted.
- **Which spell checker: the system API or an embedded one.** Two ways, to decide:
  - *System API*: `ISpellChecker` on Windows (through `ctypes`), Enchant on Linux (`libenchant`,
    `pyenchant`; Hunspell dictionaries of the distribution). Nothing to ship, but the languages
    available depend on the machine, and the code needs one engine per system behind a common
    interface. Linux was not tried (no Linux here).
  - *Embedded*: `spylls` (pure Python Hunspell) with the LibreOffice French and English
    dictionaries, about 0.5 to 2 MB per language (not measured; the application is 45 MB, its zip
    18.8 MB). Same code and dictionaries on every system, good French (affixes), but slow loading
    and suggestions in pure Python, and dictionary licences (LGPL / MPL) to respect. Other options
    seen: `pyspellchecker` (frequency lists, lower quality), `symspellpy` (fast, no morphology),
    LanguageTool (grammar too, but 200 MB or more with Java).
  - Either way: no grammar check ("ils mange" passes); technical words (paths, identifiers, code
    in backticks) must be skipped and a personal dictionary is needed; one language per field
    or a word accepted when known in either; keys to go to the next error, since the underline
    is not read by NVDA. To measure before deciding: load time and check time of `spylls` on 500
    words, and the weight added to the executable.
- The other suggestions of the CLI (add a directory, switch to `acceptEdits`) are ignored.
- The managed settings of an organization (`managed-settings.json`, MDM, server) are not read; they
  have the highest priority and could be shown read only like the general file (Windows path to
  find in the official documentation).
- **Environment variables of Claude Code** (the `env` key of the settings files, for example
  `CLAUDE_CODE_USE_POWERSHELL_TOOL=0`, `CLAUDE_CODE_DISABLE_WEB_FETCH=1`):
  - In the Claude tab of the Preferences (it exists: path of `claude`), the variables that only the
    general file (`~/.claude/settings.json`) handles.
  - In the Workspace settings dialog, a tab "Environment variables": a simple list of the variables
    with their state, a button to enable / disable or to give a value, a read-only text field that
    explains the selected variable, and the target file (Settings or SettingsLocal, as in the tab
    Tools).
  - The list of the variables and their explanations lives in a text file of the project, outside the
    code, like the list of tools.
  - To check before coding: the exact meaning of each variable (the list was read from the
    official page `env-vars` through a summarizer, and `CLAUDE_CODE_USE_POWERSHELL_TOOL` is only on
    the page `tools-reference`), which ones the project and local files may set (some are ignored
    there), whether a change applies to a running session, and the Windows path of the managed
    settings file (read only).
