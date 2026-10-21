# Open questions and improvements

The other files of `docs/` describe what is true and decided. Everything that is still to decide,
to verify or to improve lives here, and nowhere else. When an item is settled, move the result to
the file it belongs to and delete it from this one.

## To decide

Nothing at the moment.

## To verify

- **UI Automation notifications and JAWS.** They reach NVDA and Narrator; test JAWS, with a focusable
  progress field as a fallback if they do not.
- **Reading the usage gauge without sending a message** (no way found yet).
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

- Context menu on a message (copy, show the tools used, a table, a link), see
  `conversation-display.md`.
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
  - In Preferences, a tab "Claude" for the variables that only the general file
    (`~/.claude/settings.json`) handles.
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
