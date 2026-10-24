# Interface

## Main window

- **Conversation**: read-only view of the exchange. It takes the focus only when the user loads, sends or
  refreshes, or searches (`focus.md`); never at the end of an answer. How the
  conversation will be displayed (Markdown, navigation by headings) is in
  `conversation-display.md`. Your prompt appears as soon as it is sent, then each block of text of
  the answer.
- **Prompt**: multi-line field. Enter adds a line break; the send shortcuts are configurable
  (default Ctrl+Enter to send, Shift+Enter to send with the alternative agent).
- Buttons: *Send*, *Send with the alternative agent* (their labels show the current shortcuts) and
  *Interrupt Claude* (active only while Claude is answering; it also stops the programs Claude
  started). While Claude answers, Send is greyed; the prompt field stays usable.
- Status bar, three fields: the position of the caret among your prompts (`Message 3 of 8`), the
  step Claude works on (`Step 2 of 5: Build the module`; empty when there is none and while the
  window waits for a prompt), then the last announcement. Progress ("Claude is thinking", "Claude
  uses the tool Read", "Claude is answering", "Permission denied for the tool Bash"), the steps, the
  end of a turn ("Claude has answered", "Claude was interrupted") and the other announcements go
  where the Announcements page of the Preferences says, per category. A failure ("Claude could not
  answer: ...") is written in the status bar and opens a dialog with the details; the prompt is
  kept when Claude cannot be started.
- **Step**: when Claude puts a task of its list in progress (`TaskUpdate` with the status
  `in_progress`, seen with the real CLI), the step is the place of that task in the task files of the
  conversation (`core/claude/tasks.py`). It is announced (category "Step in progress", instead of "Claude
  uses the tool TaskUpdate") and kept in the second status field until the end of the turn. A task
  that is not in the files gives the normal progress.
- Window title: `<conversation> - <workspace> - WxClaude`, the parts that exist.

## Menus

**File**: Open workspace (Ctrl+O), Open from Claude projects, Export the conversation, Recent
(name, then where it is), Preferences, Quit (Ctrl+Q); Preferences and Quit are the last two.

**Conversation**: New conversation (Ctrl+N), Resume a conversation (Ctrl+Shift+O), Refresh the
conversation (F5, reads the session file again; the focus goes to the conversation, the caret to
the last prompt), Rename (the CLI renames the session), New conversation branch (see "Branch and delete"),
Delete the conversation (see "Branch and delete"), Summary of the tools under the answers (a
check item, see the conversation display), Interrupt Claude (Ctrl+Shift+I), Modify the agent, and the
submenu **Search** (see below).

**Tools**: Task list (Ctrl+T, as in the CLI), Plan (no shortcut), Claude usage (Ctrl+Shift+U), Open
the workspace folder (in the file explorer; needs a workspace), Workspace settings (needs a
workspace).

The context menu of the conversation (tools used, table, links, copy) is in
`conversation-display.md`, with the usage dialog.

## Task list

*Tools > Task list…* shows the tasks Claude wrote for the current conversation, read from
`<config>/tasks/<conversation id>/*.json` (read only; `CLAUDE_CONFIG_DIR` is honoured). A list, one
task per line in number order: number, subject, state (*pending*, *in progress*, *completed*) and,
when it still waits for tasks that are not completed, `blocked by 3 4`; for example `2, Build, pending,
blocked by 1`. A read-only field below gives the description of the selected task. A file that is not
a readable task is named on the last line of the list. Without any task the list says so. The
dialog shows what the folder holds when it opens; it is not refreshed while it is open.

## Plan

*Tools > Plan…* shows the plans Claude wrote in the current conversation (in the mode *Plan only
(plan)*), to read them; there is nothing to approve here. It needs a conversation, like the task
list, and is never greyed for lack of a plan: without any, the list says "No plan in this
conversation yet.". A list, one plan per line (the name of its file, `<config>/plans/<name>.md`;
`, file missing, text from the session` when the file is gone), the last one selected; a read-only
field below gives the text of the selected plan. The plans are the `Write` calls of the session file
to the plans folder, so it is the same with the stdio protocol and with the HTTP hook
(`claude-cli.md`, "Permission channels"); the text is read from the file, which Claude may have
edited since. The dialog shows what exists when it opens.

**Help**: WxClaude help (F1), About. The help page is one plain HTML file per language
(`src/wxclaude/help/fr.html`, `en.html`, package data; no CSS, no script) that F1 opens as it is in
the default browser; a language without a page falls back on English, and a missing page is
reported. The text is written in Markdown in `MakeHelp/` (`Aide.md` for French, `Help.md` for
English, with the same headings: a test checks it) and
`MakeHelp/make_help.py` turns it into the HTML page: `.venv\Scripts\python.exe MakeHelp\make_help.py
[source.md] [language]` (defaults: `Aide.md`, `fr`; for English `MakeHelp\make_help.py
MakeHelp\Help.md en`), to run again after every edit and once per language. A test fails when a page
of the package is not the conversion of its text. The text only describes what exists and was tested, names no shortcut, and is updated with
the features.

## Permissions

When Claude wants to run a tool that the permission mode of the agent does not allow, a dialog asks
(the status bar and the announcements say "Claude asks permission for the tool ..."):

- a read-only field describes the request (tool, what it is for, the path, the arguments); it has
  the initial focus, so a screen reader reads it and a stray Enter does nothing;
- a field for the explanation sent to Claude if the user denies;
- *Allow*, *Always allow this* (only when the CLI proposes a rule to remember) and *Deny*. Esc or
  closing the dialog is a denial. The answer is announced ("Permission granted / refused for the
  tool ...").

*Always allow this* writes an *allow* rule (for example `Bash(touch x)` or `Edit`) in the personal
settings file of the workspace, `.claude/settings.local.json`, as the CLI itself does: Claude does
not ask about it again, in this message or in the next ones (and neither does the CLI in a terminal).
If the file cannot be read (invalid JSON) it is left as it is and an error says so. A tool that was
denied without a question (a *deny* rule, or the `dontAsk` mode) is only shown as progress.

With the HTTP hook channel (Preferences, Claude), the CLI stops waiting after the waiting time
and denies the tool: if the dialog is still open it is closed, and "The question about the tool ...
expired: Claude denied the tool." is announced. A tool refused by the user's own answer is announced
once ("Permission refused ...", not "Permission denied ..." as well).

## Workspace settings

*Tools > Workspace settings...* edits the permission rules that Claude Code keeps in the `.claude`
folder of the workspace. It is a dialog with one tab for now, **Tools**:

- **Target file** (list): *Settings* (`.claude/settings.json`, shared and versioned, the default)
  or *SettingsLocal* (`.claude/settings.local.json`, personal). With the preference "Change the
  tools only in the local file, which is not versioned" only *SettingsLocal* is proposed, so a
  developer who shares the project with others using the CLI never modifies the shared file. A
  read-only field says which file will be modified and whether it is versioned, and that the
  general file (`~/.claude/settings.json`) is only read.
- **Tools** (list): the tools Claude knows (the file `src/wxclaude/data/tools.txt` and the tools
  that the files name). One line per tool: its name, then the pieces of information that have a
  value, separated by commas: the approval it has in the target file (*Allow*, *Ask*, *Deny*), the
  approval that prevails and the file it comes from when it differs ("Deny by general"), and
  "with rules" when rules with a specifier exist (not evaluated). Example:
  `Bash Allow, Deny by general, with rules`. A tool with nothing to say shows only its name.
  The files are *general*, *Settings* and *SettingsLocal*; the prevailing approval is *Deny*, then
  *Ask*, then *Allow*, whatever the file.
- Buttons **Deny**, **Ask**, **Allow**: give the selected tool one rule without specifier in the target
  file, replacing the ones it had there. Greyed when the file cannot be modified.
- **Rules of the target file** (list): every rule, "Deny, Bash(git *)", sorted by tool then by
  approval, and **Remove** (this is also how a tool goes back to "no rule").
- **Rule to add**, **Approval of the rule** (list) and **Add the rule**: any rule as typed. Rules are
  not checked and may contradict each other.
- OK writes the files that changed (atomically, the other keys of a file are kept, a file that
  cannot be read is never overwritten); Cancel writes nothing. The rules apply to the messages sent
  afterwards.

## Search

Submenu *Search* of the Conversation menu: *Find…* (Ctrl+F), *Find next* (F3), *Find
previous* (Shift+F3); all need a conversation. They look in the text of the conversation view (what
is displayed, titles included).

- *Find…* opens a dialog: the term (the previous one is proposed and selected), *Match case*,
  *Whole words only*. An empty term is refused. OK searches forward from the caret.
- *Find next* / *Find previous* repeat the search of the last term in either direction; without a
  previous term they open the dialog. The search starts after the selection (before it when going
  backwards), so repeating it walks through the occurrences. It does not wrap around.
- An occurrence is selected and the view gets the focus (`focus.md`); the whole line that holds it is announced
  (status bar and UI Automation). When there is no more occurrence in the direction asked,
  "No next occurrence of ..." or "No previous occurrence of ..." goes where the category
  "Unsuccessful search" says: nothing, a message (default; said to the screen reader, not written
  in the status bar) or a message dialog. The status bar keeps the messages of the progress of
  Claude, the answers to a permission and the refresh (`accessibility.md`).
- **Gauge alerts**: the 5-hour gauge and the weekly gauge (`unifiedWindows` of the `rate_limit_event`)
  are announced the first time they reach or pass an alert threshold (90 % for the 5 hours; 25 %,
  50 % and 75 % for the week: the early-warning thresholds of Claude Code itself, see
  `claude-cli.md`; `ALERT_THRESHOLDS` in `core/claude/usage.py`), by the category "Gauge alerts" (nothing or a message, default message):
  "Alert: the 5-hour gauge is at 91 %." and "Alert: the weekly gauge is at 76 %.". A gauge is
  announced again only after it went back under that threshold, so the windows that start again
  at 0 % (every 5 hours, every week) are announced again in an application left open. An alert is
  only said, never written in the status bar (it would stay there until the next message).
- When Claude has answered (or was interrupted) the status bar goes back to "Ready", followed by
  the 5-hour gauge when it is known: "Ready, gauge at 50 %". The weekly gauge is added once it is at
  or over its last alert threshold (75 %): "Ready, gauge at 50 %, week at 76 %"; under it, the usage
  dialog has it. This line is state, not an announcement: it does not depend on the destination of
  the gauge alerts. After a failure the status bar keeps the error.
- **Reading the gauges** (`claude-cli.md`, "Gauges without a message"): at startup, when a first
  workspace opens, and by a timer of one minute when a gauge is unknown or past its reset time,
  WxClaude reads them with `/usage`, without sending a message. It is handled like a message: both
  send buttons and the *Claude usage* item of the Tools menu are greyed, the message field of the
  status bar says "Refreshing the gauges", and *Interrupt Claude* stays available to stop it. At the
  end, success or not, the window is back to waiting for a prompt ("Ready, gauge at 50 %"). Nothing
  is shown as an error and the only thing said is a gauge alert when a threshold is reached; nothing
  is read without a workspace.

Resume lists the conversations of the workspace, the one with the most recent message first.

## What is available when

| State | Available |
|---|---|
| No workspace (first start, option off, folder gone) | Open workspace, Open from Claude projects, Recent, Quit, Preferences, About. Everything else is greyed, including the prompt and the send buttons. |
| Workspace, no conversation | The above and New conversation. |
| Conversation | Everything, except Interrupt Claude which needs an answer in progress. Refresh, Rename, Branch, Delete, the Search items, Modify the agent and Task list need a conversation; Open the workspace folder and Workspace settings only need a workspace. |

Opening another workspace closes the current conversation.

## Branch and delete

**New conversation branch** asks for a name (current name followed by `branch x`) and makes the
branch the current conversation: the text on screen stays, the focus goes to the last prompt
(`focus.md`, rule B). Its first message copies the history of the conversation into a Claude Code
session of its own (`--fork-session`); the original is left as it is. A conversation without any
message cannot be branched (an error says there is nothing to copy). Leaving a branch before its
first message forgets it, as a new conversation never sent.

**Delete the conversation** asks `Move the conversation "<name>" to the Recycle Bin?` (Yes, No; No
by default), then moves to the Recycle Bin of Windows what Claude Code keeps of it (its transcript,
the folder beside it, its file history, its tasks). The announcement `Conversation "<name>" moved
to the Recycle Bin.` follows, and the most recent conversation of the workspace is selected, else
the workspace is left without any. It is refused while Claude answers. If a file cannot be moved,
an error says so and the conversation stays.

## Names of conversations

A dialog with one field, the proposal selected, opens for: New conversation (`Conversation x`,
the number grows only when the name is accepted), Rename (current name) and New conversation
branch (current name followed by `branch x`). An empty name is refused.

The name of a conversation is the name of its Claude Code session, so Claude Code (`--resume`, the
picker, `/rename`) and WxClaude show the same one:

- A conversation that has no session yet (no message sent) only has its name in WxClaude; the first
  message gives it to the CLI with `--name` (`claude-cli.md`, "Name of a session").
- Rename on a conversation that has a session runs `/rename <name>` through the CLI
  (`ClaudeRunner.rename_session`, instant and free); if it fails the name does not change and the
  error is shown. It is refused while Claude is answering. Refresh takes a name given elsewhere.
- A session without a name is shown by the start of its identifier. WxClaude no longer stores
  names (`settings.md`).

## Agents

An agent bundles a model (listed from the least to the most powerful), an effort and a permission
mode, all three always chosen: the CLI is never left to pick one from its own settings. Two agents
are defined in Preferences > Agent: the one of a new conversation and the alternative agent, used by the
"send with the alternative agent" command; its fields can be left on "same as the conversation".
Changing the model loses the prompt cache of the conversation (measured with the CLI); changing the
effort or the permission mode does not.

## Preferences

- **General**: language (applies at the next start); at startup, open the last workspace.
- **Claude** (after General): *Automatic search for claude-p* (checked by default: `claude` is looked
  for in the PATH); *Path of claude-p* and *Select…* (file dialog), both greyed while the search is
  automatic. OK is refused, with the focus on the path, if the search is off and the path is empty
  or not a file. *Interface type* (a drop-down list, *Stdio protocol* by default or *HTTP hook*): how
  Claude's permission questions reach WxClaude, applied to the next message (the conversation can
  switch at any time). *Wait for your answer, in minutes (HTTP hook)* (1 to 10, 10 by default) is
  greyed with the stdio protocol. What the HTTP hook cannot do is in `claude-cli.md`,
  "Permission channels".
- **Workspace**: hide the system messages (checked by default): the noise the CLI writes in
  a session, such as the answer "No response requested.", is not displayed; change the tools only
  in the local file, which is not versioned (unchecked by default, see Workspace settings).
- **Agent**: list of the two agents, their fields, the implication of each permission level and the
  cache notice.
- **Shortcuts**: list of commands, field to press the new shortcut, restore the default, no
  shortcut. A shortcut is refused if it is invalid, reserved, standard or already used.
- **Announcements**: how announcements are sent (none, UI Automation on Windows); the list of the
  announcement categories with their destination, a list to change the destination of the selected
  category and a button to restore its default (changes apply with OK). Destinations: *No
  announcement*, *Message*, *Read the line* (movement in the conversation, headings), *Dialog box* (unsuccessful search), *Message.wav*,
  *Permission.wav*. Defaults: Message, except
  the end of an answer (Message.wav) and the question of permission (Permission.wav). See `accessibility.md`.
