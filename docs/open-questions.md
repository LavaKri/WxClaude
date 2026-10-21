# Open questions and improvements

The other files of `docs/` describe what is true and decided. Everything that is still to decide,
to verify or to improve lives here, and nowhere else. When an item is settled, move the result to
the file it belongs to and delete it from this one.

## To decide

- **Dialogue mode with claude-p** (list in the Claude tab of the Preferences). WxClaude only has one
  mode today: the CLI waits for the answer to its permission question (stdio control protocol). The
  other mode of the project the idea comes from is "stop Claude, then resume it after the answer"
  (the CLI denies, the application resumes with the tool allowed): it would have to be built to
  be offered.

## To verify

- **UI Automation notifications and JAWS.** They reach NVDA and Narrator; test JAWS, with a focusable
  progress field as a fallback if they do not.
- **Reading the usage gauge without sending a message** (no way found yet).
- **Unit of the gauges.** `utilization` of `rate_limit_event` is read as a fraction (0.74 shown as
  74 %); compare with `/usage` in the CLI.
- **Cost of a resumed message.** The usage dialog adds the `total_cost_usd` of each `result` to get
  the cost of the conversation; check on a resumed message that it only covers that message and not
  the whole session.
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
- **Subscription use.** Driving `claude -p` from a custom front end with a subscription login may
  be restricted by the usage policy of the provider (an API key is the safe path). Check the current
  terms.

## Improvements not done yet

- **Split the main window** (`ui/main_window.py`, over 1000 lines): its constructor and its menu
  are too long for the checks, which are switched off for this one file in `pyproject.toml`
  (`per-file-ignores`); remove that exception once it is split, following `working-rules.md`.
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
- Delete a conversation (the menu item is greyed).
- After a turn the view is rebuilt from the session file; the answer titles then show the effort
  written in the file, and none for a model that ignores it (haiku).
- *Always allow* in the permission question writes the exact rule the CLI proposes
  (`Bash(touch x)`); a wider rule is added by hand in the Workspace settings.
- The tools of the Workspace settings come from `data/tools.txt` and the files: the tools announced
  by the last run (the `tools` of the `init` line) are not added yet.
- The Workspace settings only edit the rules; other keys of the files (`env`, additional directories,
  instructions) are for later tabs.
- The other suggestions of the CLI (add a directory, switch to `acceptEdits`) are ignored.
- Rename and branch are provisional (a rename only changes the name WxClaude keeps; a branch starts
  a new identifier with the same text on screen): see milestone 6 of `roadmap.md`.
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
