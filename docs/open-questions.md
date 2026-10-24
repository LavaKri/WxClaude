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
  protocol the `ExitPlanMode` request holds the text of the plan (`input.plan`) and its result says
  where it was saved: not used.
- **HTTP hook channel, not tested yet.** `updatedPermissions` (a rule for the session), `interrupt`,
  `decision.rule` (one documentation page), a waiting time above 10 minutes (the maximum accepted
  by the CLI), `tool_use_id` (the documentation lists it, the real POST has none).
- **Screen readers and the Preferences, Screen reader tab.** The list of the announcement
  categories, the two sounds (WAV files in `wxclaude/sounds`, played with `winsound`) and the status
  bar left alone with *No announcement* are to be checked with NVDA and JAWS.
- **Screen readers and the Preferences, Claude tab.** The list *Interface type* and the spin
  control are to be checked with NVDA and JAWS.

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
- **Subscription use.** Driving `claude -p` from a custom front end with a subscription login may
  be restricted by the usage policy of the provider (an API key is the safe path). Check the current
  terms.

## Improvements not done yet

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
